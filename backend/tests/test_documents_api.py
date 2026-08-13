"""Document upload and processing API tests."""

from pathlib import Path

import pytest

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "data" / "documents" / "samples"


@pytest.fixture()
def admin_headers(client, admin_user):
    response = client.post(
        "/api/auth/login",
        json={"email": "admin.user@vsit.edu.in", "password": "adminpass1"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def document_dirs(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    processed_dir = tmp_path / "processed"
    upload_dir.mkdir(exist_ok=True)
    processed_dir.mkdir(exist_ok=True)

    monkeypatch.setattr("app.services.document_service.settings.upload_directory", str(upload_dir))
    monkeypatch.setattr("app.services.document_service.settings.processed_directory", str(processed_dir))
    return upload_dir, processed_dir


def test_student_cannot_upload_document(client, student_user) -> None:
    login = client.post(
        "/api/auth/login",
        json={"email": "test.student@vsit.edu.in", "password": "studentpass"},
    )
    token = login.json()["access_token"]
    sample = SAMPLES_DIR / "attendance_policy.txt"
    response = client.post(
        "/api/admin/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("attendance_policy.txt", sample.read_bytes(), "text/plain")},
    )
    assert response.status_code == 403


def test_admin_upload_txt_document(client, admin_headers) -> None:
    sample = SAMPLES_DIR / "attendance_policy.txt"
    response = client.post(
        "/api/admin/documents/upload",
        headers=admin_headers,
        files={"file": ("attendance_policy.txt", sample.read_bytes(), "text/plain")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["document"]["status"] == "processed"
    assert data["document"]["chunk_count"] >= 1


def test_admin_list_and_get_document(client, admin_headers) -> None:
    sample = SAMPLES_DIR / "library_info.txt"
    upload = client.post(
        "/api/admin/documents/upload",
        headers=admin_headers,
        files={"file": ("library_info.txt", sample.read_bytes(), "text/plain")},
    )
    document_id = upload.json()["document"]["id"]

    listing = client.get("/api/admin/documents", headers=admin_headers)
    assert listing.status_code == 200
    assert listing.json()["total"] >= 1

    detail = client.get(f"/api/admin/documents/{document_id}", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["chunks"]
    assert "library" in detail.json()["chunks"][0]["content"].lower()


def test_admin_delete_document(client, admin_headers) -> None:
    sample = SAMPLES_DIR / "examination_info.txt"
    upload = client.post(
        "/api/admin/documents/upload",
        headers=admin_headers,
        files={"file": ("examination_info.txt", sample.read_bytes(), "text/plain")},
    )
    document_id = upload.json()["document"]["id"]

    delete = client.delete(f"/api/admin/documents/{document_id}", headers=admin_headers)
    assert delete.status_code == 200

    detail = client.get(f"/api/admin/documents/{document_id}", headers=admin_headers)
    assert detail.status_code == 404


def test_upload_unsupported_format(client, admin_headers) -> None:
    response = client.post(
        "/api/admin/documents/upload",
        headers=admin_headers,
        files={"file": ("notes.exe", b"fake-binary", "application/octet-stream")},
    )
    assert response.status_code == 400


def test_attendance_question_content_is_chunked(client, admin_headers) -> None:
    sample = SAMPLES_DIR / "attendance_policy.txt"
    upload = client.post(
        "/api/admin/documents/upload",
        headers=admin_headers,
        files={"file": ("attendance_policy.txt", sample.read_bytes(), "text/plain")},
    )
    document_id = upload.json()["document"]["id"]
    detail = client.get(f"/api/admin/documents/{document_id}", headers=admin_headers)
    combined = " ".join(chunk["content"] for chunk in detail.json()["chunks"]).lower()
    assert "attendance" in combined
    assert "examination" in combined or "semester" in combined
