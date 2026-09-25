"""RAG chatbot pipeline orchestrating query processing, retrieval, and LLM generation."""

import json
import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import ChatMessage, ChatSession, User
from app.schemas.chat import SourceCitation
from app.services.intent_service import IntentServiceError, predict_intent_with_confidence
from app.services.llm_service import (
    LLMServiceError,
    NO_CONTEXT_ANSWER,
    SYSTEM_PROMPT,
    build_rag_user_prompt,
    generate_completion,
)
from app.services.query_service import (
    log_rag_debug,
    match_conversational,
    process_query,
)
from app.services.retrieval_service import RetrievedChunk, get_vector_store

logger = logging.getLogger(__name__)
settings = get_settings()


class ChatbotServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class ChatbotResult:
    answer: str
    intent: str
    sources: list[SourceCitation]
    session_id: int
    message_id: int


def _build_sources(chunks: list[RetrievedChunk]) -> list[SourceCitation]:
    seen: set[tuple[str, int | None]] = set()
    sources: list[SourceCitation] = []
    for chunk in chunks:
        key = (chunk.filename, chunk.page_number)
        if key in seen:
            continue
        seen.add(key)
        sources.append(SourceCitation(document=chunk.filename, page=chunk.page_number))
    return sources


def _build_context(chunks: list[RetrievedChunk]) -> str:
    sections: list[str] = []
    for chunk in chunks:
        page_label = f"Page {chunk.page_number}" if chunk.page_number else "Page N/A"
        section_label = f" | Section: {chunk.section}" if chunk.section else ""
        category_label = f" | Category: {chunk.category}" if chunk.category else ""
        sections.append(
            f"[Source: {chunk.filename} | {page_label}{section_label}{category_label}]\n"
            f"{chunk.content.strip()}"
        )
    return "\n\n".join(sections)


def _serialize_sources(sources: list[SourceCitation]) -> str | None:
    if not sources:
        return None
    return json.dumps([source.model_dump() for source in sources])


def _deserialize_sources(raw: str | None) -> list[SourceCitation]:
    if not raw:
        return []
    data = json.loads(raw)
    return [SourceCitation(**item) for item in data]


def _get_or_create_session(db: Session, user: User, session_id: int | None, question: str) -> ChatSession:
    if session_id is not None:
        session = (
            db.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == user.id)
            .first()
        )
        if session is None:
            raise ChatbotServiceError("Chat session not found", status_code=404)
        return session

    title = question.strip()[:60] + ("..." if len(question.strip()) > 60 else "")
    session = ChatSession(user_id=user.id, title=title or "New Chat")
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _get_recent_history(db: Session, session: ChatSession) -> list[tuple[str, str]]:
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(settings.chat_history_window * 2)
        .all()
    )
    chronological = list(reversed(messages))
    return [(message.role, message.message) for message in chronological]


def _save_message(
    db: Session,
    *,
    user: User,
    session: ChatSession,
    role: str,
    message: str,
    intent: str | None = None,
    sources: list[SourceCitation] | None = None,
) -> ChatMessage:
    chat_message = ChatMessage(
        user_id=user.id,
        session_id=session.id,
        role=role,
        message=message,
        intent=intent,
        sources_json=_serialize_sources(sources or []),
    )
    db.add(chat_message)
    db.commit()
    db.refresh(chat_message)
    return chat_message


def create_chat_session(db: Session, user: User, title: str = "New Chat") -> ChatSession:
    session = ChatSession(user_id=user.id, title=title)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _respond_without_rag(
    db: Session,
    *,
    user: User,
    session: ChatSession,
    answer: str,
    intent: str,
) -> ChatbotResult:
    assistant_message = _save_message(
        db,
        user=user,
        session=session,
        role="assistant",
        message=answer,
        intent=intent,
    )
    return ChatbotResult(
        answer=answer,
        intent=intent,
        sources=[],
        session_id=session.id,
        message_id=assistant_message.id,
    )


def process_chat_message(db: Session, user: User, question: str, session_id: int | None = None) -> ChatbotResult:
    cleaned_question = question.strip()
    if not cleaned_question:
        raise ChatbotServiceError("Question cannot be empty")

    session = _get_or_create_session(db, user, session_id, cleaned_question)
    history_before = _get_recent_history(db, session)
    _save_message(db, user=user, session=session, role="user", message=cleaned_question)

    conversational = match_conversational(cleaned_question)
    if conversational is not None:
        log_rag_debug(
            question=cleaned_question,
            intent="general",
            raw_intent="general",
            confidence=1.0,
            rewritten_query=cleaned_question,
            is_broad=False,
            top_chunks=[],
            llm_called=False,
        )
        return _respond_without_rag(
            db,
            user=user,
            session=session,
            answer=conversational.response,
            intent="general",
        )

    try:
        intent_result = predict_intent_with_confidence(cleaned_question)
    except IntentServiceError as exc:
        raise ChatbotServiceError(str(exc), status_code=503) from exc

    intent = str(intent_result["intent"])
    raw_intent = str(intent_result["raw_intent"])
    confidence = float(intent_result["confidence"])
    response_intent = raw_intent
    intent_hint = raw_intent if raw_intent not in {"general"} else None
    if confidence < settings.intent_confidence_threshold:
        intent_hint = None

    processed = process_query(
        cleaned_question,
        history=history_before,
        intent_hint=intent_hint,
    )

    retrieved_chunks = get_vector_store().search(
        processed.retrieval_query,
        expanded_queries=processed.expanded_queries,
        intent_hint=intent_hint,
        is_broad=processed.is_broad,
    )

    if not retrieved_chunks:
        log_rag_debug(
            question=cleaned_question,
            intent=intent,
            raw_intent=raw_intent,
            confidence=confidence,
            rewritten_query=processed.retrieval_query,
            is_broad=processed.is_broad,
            top_chunks=[],
            llm_called=False,
        )
        return _respond_without_rag(
            db,
            user=user,
            session=session,
            answer=NO_CONTEXT_ANSWER,
            intent=response_intent,
        )

    sources = _build_sources(retrieved_chunks)
    context = _build_context(retrieved_chunks)
    user_prompt = build_rag_user_prompt(
        cleaned_question,
        context,
        conversation_context=processed.conversation_context,
        is_broad=processed.is_broad,
    )

    try:
        answer = generate_completion(SYSTEM_PROMPT, user_prompt)
    except LLMServiceError:
        raise

    log_rag_debug(
        question=cleaned_question,
        intent=intent,
        raw_intent=raw_intent,
        confidence=confidence,
        rewritten_query=processed.retrieval_query,
        is_broad=processed.is_broad,
        top_chunks=retrieved_chunks,
        llm_called=True,
    )

    assistant_message = _save_message(
        db,
        user=user,
        session=session,
        role="assistant",
        message=answer,
        intent=response_intent,
        sources=sources,
    )

    return ChatbotResult(
        answer=answer,
        intent=response_intent,
        sources=sources,
        session_id=session.id,
        message_id=assistant_message.id,
    )


def list_user_sessions(db: Session, user: User) -> list[ChatSession]:
    return (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )


def get_session_detail(db: Session, user: User, session_id: int) -> ChatSession | None:
    return (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == user.id)
        .first()
    )


def message_to_response(message: ChatMessage):
    from app.schemas.chat import ChatMessageResponse

    return ChatMessageResponse(
        id=message.id,
        role=message.role,
        message=message.message,
        intent=message.intent,
        sources=_deserialize_sources(message.sources_json),
        created_at=message.created_at,
    )
