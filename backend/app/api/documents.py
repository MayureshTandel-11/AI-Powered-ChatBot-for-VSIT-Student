"""Admin document management routes."""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.db.database import get_db
from app.db.models import Document, User
from app.schemas.documents import (
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadResponse,
)
from app.schemas.auth import MessageResponse
from app.services.document_service import (
    DocumentServiceError,
    delete_document,
    get_document,
    list_documents,
    upload_and_process,
)
from app.services.retrieval_service import get_vector_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> DocumentUploadResponse:
    content = await file.read()
    try:
        document = upload_and_process(db, file, content)
    except DocumentServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return DocumentUploadResponse(
        message="Document uploaded and processed successfully",
        document=DocumentResponse.model_validate(document),
    )


@router.get("", response_model=DocumentListResponse)
def get_documents(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> DocumentListResponse:
    documents = list_documents(db)
    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(doc) for doc in documents],
        total=len(documents),
    )


@router.get("/{document_id}", response_model=DocumentDetailResponse)
def get_document_detail(
    document_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> DocumentDetailResponse:
    document = get_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return DocumentDetailResponse.model_validate(document)


@router.delete("/{document_id}", response_model=MessageResponse)
def remove_document(
    document_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> MessageResponse:
    document = get_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    delete_document(db, document)
    return MessageResponse(message="Document deleted successfully")


@router.post("/reindex", response_model=MessageResponse)
def reindex_documents(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> MessageResponse:
    """Rebuild the FAISS vector index from all processed documents."""
    count = get_vector_store().rebuild_from_database(db)
    return MessageResponse(message=f"Vector index rebuilt with {count} chunks")
