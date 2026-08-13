"""Pydantic schemas for chat endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class SourceCitation(BaseModel):
    document: str
    page: int | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: int | None = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Message cannot be empty")
        return cleaned


class ChatResponse(BaseModel):
    answer: str
    intent: str
    sources: list[SourceCitation] = Field(default_factory=list)
    session_id: int
    message_id: int


class ChatSessionCreateResponse(BaseModel):
    session_id: int
    title: str


class ChatMessageResponse(BaseModel):
    id: int
    role: str
    message: str
    intent: str | None = None
    sources: list[SourceCitation] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatSessionSummary(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int

    model_config = {"from_attributes": True}


class ChatHistoryResponse(BaseModel):
    sessions: list[ChatSessionSummary]
    total: int


class ChatSessionDetailResponse(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessageResponse]
