"""Chat and RAG pipeline tests."""

from pathlib import Path

import pytest

from app.core.config import BACKEND_ROOT
from app.db.models import Document, DocumentChunk
from app.ml.training import train_and_save
from app.services.intent_service import reset_intent_classifier
from app.services.retrieval_service import VectorStore, get_vector_store

SAMPLES_DIR = BACKEND_ROOT / "data" / "documents" / "samples"


@pytest.fixture()
def student_headers(client, student_user):
    login = client.post(
        "/api/auth/login",
        json={"email": "test.student@vsit.edu.in", "password": "studentpass"},
    )
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def trained_intent_model(tmp_path, monkeypatch):
    model_path = tmp_path / "intent_classifier.joblib"
    metrics_path = tmp_path / "intent_metrics.json"
    train_and_save(model_path=model_path, metrics_path=metrics_path)
    monkeypatch.setattr("app.services.intent_service.settings.intent_model_path", str(model_path))
    monkeypatch.setattr("app.services.intent_service.settings.intent_metrics_path", str(metrics_path))
    reset_intent_classifier()
    yield
    reset_intent_classifier()


def _seed_attendance_document(db_session) -> None:
    text = (SAMPLES_DIR / "attendance_policy.txt").read_text(encoding="utf-8")
    document = Document(
        filename="attendance_policy.txt",
        file_path=str(SAMPLES_DIR / "attendance_policy.txt"),
        document_type="txt",
        status="processed",
        chunk_count=1,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    chunk = DocumentChunk(
        document_id=document.id,
        chunk_id=0,
        content=text,
        page_number=1,
        source=document.filename,
        word_count=len(text.split()),
    )
    db_session.add(chunk)
    db_session.commit()

    get_vector_store().rebuild_from_database(db_session)


def test_chat_requires_authentication(client) -> None:
    response = client.post("/api/chat", json={"message": "What is attendance policy?"})
    assert response.status_code == 401


def test_off_topic_question(client, student_headers, trained_intent_model) -> None:
    response = client.post(
        "/api/chat",
        headers=student_headers,
        json={"message": "Who is the current president of the United States?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "general"
    assert "college" in data["answer"].lower()
    assert data["sources"] == []


def test_no_context_response(client, student_headers, trained_intent_model, db_session) -> None:
    response = client.post(
        "/api/chat",
        headers=student_headers,
        json={"message": "What is the minimum attendance requirement?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "attendance"
    assert "couldn't find" in data["answer"].lower()


def test_rag_chat_returns_sources_with_mock_llm(
    client,
    student_headers,
    trained_intent_model,
    db_session,
    monkeypatch,
) -> None:
    _seed_attendance_document(db_session)

    def mock_generate(system_prompt: str, user_prompt: str) -> str:
        assert "attendance" in user_prompt.lower()
        return "Students must maintain the minimum attendance requirement specified in the academic regulations."

    monkeypatch.setattr("app.services.chatbot_service.generate_completion", mock_generate)

    response = client.post(
        "/api/chat",
        headers=student_headers,
        json={"message": "What is the minimum attendance requirement?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "attendance"
    assert data["sources"]
    assert data["sources"][0]["document"] == "attendance_policy.txt"
    assert "attendance" in data["answer"].lower()


def test_chat_history_and_session_detail(
    client,
    student_headers,
    trained_intent_model,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.services.chatbot_service.generate_completion",
        lambda system_prompt, user_prompt: "General help response",
    )

    first = client.post(
        "/api/chat",
        headers=student_headers,
        json={"message": "Hello"},
    )
    session_id = first.json()["session_id"]

    client.post(
        "/api/chat",
        headers=student_headers,
        json={"message": "Tell me about exams", "session_id": session_id},
    )

    history = client.get("/api/chat/history", headers=student_headers)
    assert history.status_code == 200
    assert history.json()["total"] >= 1

    detail = client.get(f"/api/chat/{session_id}", headers=student_headers)
    assert detail.status_code == 200
    assert len(detail.json()["messages"]) >= 2


def test_create_chat_session(client, student_headers) -> None:
    response = client.post("/api/chat/session", headers=student_headers)
    assert response.status_code == 201
    assert response.json()["session_id"]


def test_empty_question_rejected(client, student_headers, trained_intent_model) -> None:
    response = client.post("/api/chat", headers=student_headers, json={"message": "   "})
    assert response.status_code == 422


def test_unrelated_geography_question(client, student_headers, trained_intent_model) -> None:
    response = client.post(
        "/api/chat",
        headers=student_headers,
        json={"message": "What is the capital of Japan?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "general"
    assert "college" in data["answer"].lower()
    assert data["sources"] == []


def test_student_cannot_access_other_users_session(
    client,
    db_session,
    student_user,
    trained_intent_model,
    monkeypatch,
) -> None:
    from app.core.security import hash_password
    from app.db.models import User

    other = User(
        name="Other Student",
        email="other.student@vsit.edu.in",
        password_hash=hash_password("otherpass1"),
        role="student",
        email_verified=True,
    )
    db_session.add(other)
    db_session.commit()

    student_login = client.post(
        "/api/auth/login",
        json={"email": "test.student@vsit.edu.in", "password": "studentpass"},
    )
    student_headers = {"Authorization": f"Bearer {student_login.json()['access_token']}"}

    other_login = client.post(
        "/api/auth/login",
        json={"email": "other.student@vsit.edu.in", "password": "otherpass1"},
    )
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    monkeypatch.setattr(
        "app.services.chatbot_service.generate_completion",
        lambda system_prompt, user_prompt: "Helpful response",
    )

    created = client.post(
        "/api/chat",
        headers=student_headers,
        json={"message": "Hello"},
    )
    session_id = created.json()["session_id"]

    forbidden = client.get(f"/api/chat/{session_id}", headers=other_headers)
    assert forbidden.status_code == 404
