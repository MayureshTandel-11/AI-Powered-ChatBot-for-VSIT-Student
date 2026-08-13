"""Student chat API routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.schemas.chat import (
    ChatHistoryResponse,
    ChatRequest,
    ChatResponse,
    ChatSessionCreateResponse,
    ChatSessionDetailResponse,
    ChatSessionSummary,
)
from app.services.chatbot_service import (
    ChatbotServiceError,
    create_chat_session,
    get_session_detail,
    list_user_sessions,
    message_to_response,
    process_chat_message,
)
from app.services.llm_service import LLMServiceError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def send_message(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    try:
        result = process_chat_message(
            db,
            current_user,
            payload.message,
            session_id=payload.session_id,
        )
    except ChatbotServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except LLMServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    logger.info("Chat response generated for user=%s session=%s", current_user.email, result.session_id)
    return ChatResponse(
        answer=result.answer,
        intent=result.intent,
        sources=result.sources,
        session_id=result.session_id,
        message_id=result.message_id,
    )


@router.post("/session", response_model=ChatSessionCreateResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatSessionCreateResponse:
    session = create_chat_session(db, current_user)
    return ChatSessionCreateResponse(session_id=session.id, title=session.title)


@router.get("/history", response_model=ChatHistoryResponse)
def chat_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatHistoryResponse:
    sessions = list_user_sessions(db, current_user)
    summaries = [
        ChatSessionSummary(
            id=session.id,
            title=session.title,
            created_at=session.created_at,
            updated_at=session.updated_at,
            message_count=len(session.messages),
        )
        for session in sessions
    ]
    return ChatHistoryResponse(sessions=summaries, total=len(summaries))


@router.get("/{session_id}", response_model=ChatSessionDetailResponse)
def get_chat_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatSessionDetailResponse:
    session = get_session_detail(db, current_user, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")

    return ChatSessionDetailResponse(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[message_to_response(message) for message in session.messages],
    )
