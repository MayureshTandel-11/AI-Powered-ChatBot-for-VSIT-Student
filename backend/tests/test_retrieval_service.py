"""Tests for FAISS vector retrieval."""

from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import Document, DocumentChunk
from app.services.retrieval_service import VectorStore

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "data" / "documents" / "samples"


def _seed_attendance_document(db: Session) -> Document:
    text = (SAMPLES_DIR / "attendance_management.txt").read_text(encoding="utf-8")
    document = Document(
        filename="attendance_management.txt",
        file_path=str(SAMPLES_DIR / "attendance_management.txt"),
        document_type="txt",
        status="processed",
        chunk_count=1,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    chunk = DocumentChunk(
        document_id=document.id,
        chunk_id=0,
        content=text,
        page_number=1,
        source=document.filename,
        word_count=len(text.split()),
    )
    db.add(chunk)
    db.commit()
    return document


def test_vector_store_indexes_and_searches_attendance(db_session) -> None:
    _seed_attendance_document(db_session)
    store = VectorStore()
    indexed = store.rebuild_from_database(db_session)
    assert indexed == 1
    assert store.is_available()

    results = store.search("What is the attendance requirement?")
    assert results
    combined = " ".join(result.content.lower() for result in results)
    assert "attendance" in combined


def test_reindex_api(client, admin_user, db_session) -> None:
    _seed_attendance_document(db_session)

    login = client.post(
        "/api/auth/login",
        json={"email": "admin.user@vsit.edu.in", "password": "adminpass1"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.post("/api/admin/documents/reindex", headers=headers)
    assert response.status_code == 200
    assert "rebuilt with 1 chunks" in response.json()["message"].lower()

    store = VectorStore()
    store.load()
    results = store.search("attendance requirement")
    assert results
