"""Pydantic schemas for document management."""

from datetime import datetime

from pydantic import BaseModel, Field


class DocumentChunkResponse(BaseModel):
    chunk_id: int
    content: str
    page_number: int | None
    source: str
    word_count: int

    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
    id: int
    filename: str
    document_type: str
    status: str
    chunk_count: int
    uploaded_at: datetime
    processed_at: datetime | None

    model_config = {"from_attributes": True}


class DocumentDetailResponse(DocumentResponse):
    chunks: list[DocumentChunkResponse] = Field(default_factory=list)


class DocumentUploadResponse(BaseModel):
    message: str
    document: DocumentResponse


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int
