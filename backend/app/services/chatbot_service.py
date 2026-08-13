"""RAG chatbot pipeline orchestrating intent, retrieval, and LLM generation."""

import json
import logging
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import ChatMessage, ChatSession, User
from app.schemas.chat import SourceCitation
from app.services.intent_service import IntentServiceError, classify_intent
from app.services.llm_service import SYSTEM_PROMPT, LLMServiceError, generate_completion
from app.services.retrieval_service import RetrievedChunk, get_vector_store

logger = logging.getLogger(__name__)

OFF_TOPIC_PATTERNS = [
    r"\bpresident of the united states\b",
    r"\bweather\b",
    r"\btell me a joke\b",
    r"\bwho won the world cup\b",
    r"\bprime minister of\b",
    r"\bcapital of\b",
]

GREETING_PATTERNS = [
    r"^(hi|hello|hey|good morning|good evening|good afternoon)\b",
    r"\bthank you\b",
    r"\bthanks\b",
]

NO_CONTEXT_ANSWER = (
    "I couldn't find this information in the college knowledge base. "
    "Please contact the relevant college department for the latest information."
)

OFF_TOPIC_ANSWER = (
    "I'm a college student assistant and can help with college-related questions such as "
    "attendance, exams, library, fees, departments, and academic rules. "
    "Please ask me something about your college."
)

GENERAL_HELP_ANSWER = (
    "I'm your college AI assistant. Ask me about attendance, examinations, library services, "
    "fees, scholarships, departments, faculty, timetables, hostel, admission, or academic rules."
)


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


def _is_off_topic(question: str) -> bool:
    normalized = question.lower()
    return any(re.search(pattern, normalized) for pattern in OFF_TOPIC_PATTERNS)


def _is_greeting(question: str) -> bool:
    normalized = question.lower().strip()
    return any(re.search(pattern, normalized) for pattern in GREETING_PATTERNS)


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
        sections.append(
            f"[Source: {chunk.filename} | {page_label}]\n{chunk.content.strip()}"
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


def process_chat_message(db: Session, user: User, question: str, session_id: int | None = None) -> ChatbotResult:
    cleaned_question = question.strip()
    if not cleaned_question:
        raise ChatbotServiceError("Question cannot be empty")

    session = _get_or_create_session(db, user, session_id, cleaned_question)
    _save_message(db, user=user, session=session, role="user", message=cleaned_question)

    if _is_off_topic(cleaned_question):
        assistant_message = _save_message(
            db,
            user=user,
            session=session,
            role="assistant",
            message=OFF_TOPIC_ANSWER,
            intent="general",
        )
        return ChatbotResult(
            answer=OFF_TOPIC_ANSWER,
            intent="general",
            sources=[],
            session_id=session.id,
            message_id=assistant_message.id,
        )

    try:
        intent_prediction = classify_intent(cleaned_question)
    except IntentServiceError as exc:
        raise ChatbotServiceError(str(exc), status_code=503) from exc

    intent = intent_prediction.intent
    logger.info("Chat request classified as intent=%s user=%s", intent, user.email)

    if intent == "general":
        if _is_off_topic(cleaned_question):
            answer = OFF_TOPIC_ANSWER
        elif _is_greeting(cleaned_question):
            answer = "Hello! I'm your college AI assistant. How can I help you with college-related information today?"
        else:
            answer = GENERAL_HELP_ANSWER

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

    retrieved_chunks = get_vector_store().search(cleaned_question)
    if not retrieved_chunks:
        assistant_message = _save_message(
            db,
            user=user,
            session=session,
            role="assistant",
            message=NO_CONTEXT_ANSWER,
            intent=intent,
        )
        return ChatbotResult(
            answer=NO_CONTEXT_ANSWER,
            intent=intent,
            sources=[],
            session_id=session.id,
            message_id=assistant_message.id,
        )

    sources = _build_sources(retrieved_chunks)
    context = _build_context(retrieved_chunks)
    user_prompt = (
        f"College knowledge context:\n{context}\n\n"
        f"Student question:\n{cleaned_question}\n\n"
        "Provide a grounded answer using only the context above."
    )

    try:
        answer = generate_completion(SYSTEM_PROMPT, user_prompt)
    except LLMServiceError:
        raise

    assistant_message = _save_message(
        db,
        user=user,
        session=session,
        role="assistant",
        message=answer,
        intent=intent,
        sources=sources,
    )

    return ChatbotResult(
        answer=answer,
        intent=intent,
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
