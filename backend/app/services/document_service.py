"""Document upload, extraction, chunking, and persistence."""

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Document, DocumentChunk
from app.services.chunking_service import chunk_pages
from app.services.document_loaders import (
    EmptyDocumentError,
    UnsupportedDocumentTypeError,
    extract_text_from_file,
    get_document_type,
)
from app.services.retrieval_service import get_vector_store

logger = logging.getLogger(__name__)
settings = get_settings()


class DocumentServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _safe_filename(filename: str) -> str:
    name = Path(filename).name
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return name or "document.txt"


def validate_upload(file: UploadFile, content: bytes) -> str:
    if not file.filename:
        raise DocumentServiceError("Filename is required")

    document_type = get_document_type(file.filename)
    if document_type not in settings.allowed_extensions:
        raise DocumentServiceError(
            f"Unsupported file format. Allowed: {', '.join(sorted(settings.allowed_extensions))}"
        )

    if not content:
        raise DocumentServiceError("Uploaded file is empty")

    if len(content) > settings.max_upload_size_bytes:
        raise DocumentServiceError(
            f"File too large. Maximum size is {settings.max_upload_size_mb} MB",
            status_code=413,
        )

    return document_type


def _ensure_directories() -> None:
    Path(settings.upload_directory).mkdir(parents=True, exist_ok=True)
    Path(settings.processed_directory).mkdir(parents=True, exist_ok=True)


def save_upload_file(filename: str, content: bytes) -> Path:
    _ensure_directories()
    safe_name = _safe_filename(filename)
    stored_name = f"{uuid.uuid4().hex}_{safe_name}"
    destination = Path(settings.upload_directory) / stored_name
    destination.write_bytes(content)
    return destination


def process_document_record(db: Session, document: Document, index_vectors: bool = True) -> Document:
    file_path = Path(document.file_path)
    if not file_path.exists():
        document.status = "failed"
        db.commit()
        raise DocumentServiceError("Stored document file not found", status_code=404)

    document.status = "processing"
    db.commit()

    try:
        extracted = extract_text_from_file(file_path, document.document_type)
        pages = [(page.text, page.page_number) for page in extracted.pages]
        chunks = chunk_pages(pages, source=document.filename)

        db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()

        for chunk in chunks:
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_id=chunk.chunk_id,
                    content=chunk.content,
                    page_number=chunk.page_number,
                    source=chunk.source,
                    word_count=chunk.word_count,
                )
            )

        document.chunk_count = len(chunks)
        document.status = "processed" if chunks else "failed"
        document.processed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(document)

        _write_processed_snapshot(document, chunks)
        if index_vectors:
            get_vector_store().index_document(db, document.id)
        logger.info(
            "Processed document id=%s filename=%s chunks=%s",
            document.id,
            document.filename,
            document.chunk_count,
        )
        return document
    except (UnsupportedDocumentTypeError, EmptyDocumentError) as exc:
        document.status = "failed"
        db.commit()
        raise DocumentServiceError(str(exc)) from exc
    except DocumentServiceError:
        document.status = "failed"
        db.commit()
        raise
    except Exception as exc:
        logger.exception("Document processing failed for id=%s", document.id)
        document.status = "failed"
        db.commit()
        raise DocumentServiceError(f"Document processing failed: {exc}") from exc


def _write_processed_snapshot(document: Document, chunks) -> None:
    snapshot = {
        "document_id": document.id,
        "filename": document.filename,
        "document_type": document.document_type,
        "chunk_count": len(chunks),
        "chunks": [
            {
                "chunk_id": chunk.chunk_id,
                "page_number": chunk.page_number,
                "source": chunk.source,
                "word_count": chunk.word_count,
                "content_preview": chunk.content[:200],
            }
            for chunk in chunks
        ],
    }
    output_path = Path(settings.processed_directory) / f"document_{document.id}.json"
    output_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")


def upload_and_process(db: Session, file: UploadFile, content: bytes, index_vectors: bool = True) -> Document:
    document_type = validate_upload(file, content)
    stored_path = save_upload_file(file.filename, content)

    document = Document(
        filename=_safe_filename(file.filename),
        file_path=str(stored_path),
        document_type=document_type,
        status="uploaded",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    logger.info("Uploaded document id=%s filename=%s", document.id, document.filename)
    return process_document_record(db, document, index_vectors=index_vectors)


def list_documents(db: Session) -> list[Document]:
    return db.query(Document).order_by(Document.uploaded_at.desc()).all()


def get_document(db: Session, document_id: int) -> Document | None:
    return db.query(Document).filter(Document.id == document_id).first()


def delete_document(db: Session, document: Document) -> None:
    file_path = Path(document.file_path)
    processed_path = Path(settings.processed_directory) / f"document_{document.id}.json"
    document_id = document.id
    filename = document.filename

    db.delete(document)
    db.commit()

    get_vector_store().rebuild_from_database(db)

    if file_path.exists():
        file_path.unlink()
    if processed_path.exists():
        processed_path.unlink()

    logger.info("Deleted document id=%s filename=%s", document_id, filename)
