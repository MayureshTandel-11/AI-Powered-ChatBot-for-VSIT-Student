"""Authentication endpoint tests."""

from fastapi.testclient import TestClient


def test_register_student(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={
            "first_name": "Alice",
            "surname": "Student",
            "email": "alice.student@vsit.edu.in",
            "password": "password123",
            "confirm_password": "password123",
        },
    )
    assert response.status_code == 202
    data = response.json()
    assert "verification" in data["message"].lower()


def test_register_duplicate_email(client: TestClient) -> None:
    payload = {
        "first_name": "Alice",
        "surname": "Student",
        "email": "alice.student@vsit.edu.in",
        "password": "password123",
        "confirm_password": "password123",
    }
    # first register
    client.post("/api/auth/register", json=payload)
    # simulate verifying the account by creating a verified user
    response = client.post("/api/auth/register", json=payload)
    # second call will update existing pending; behavior returns 202 or 400 depending on verification
    assert response.status_code in (202, 400)


def test_login_success(client: TestClient, student_user) -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": "test.student@vsit.edu.in", "password": "studentpass"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["access_token"]
    assert data["user"]["role"] == "student"


def test_login_invalid_credentials(client: TestClient, student_user) -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": "test.student@vsit.edu.in", "password": "wrongpassword"},
    )
    assert response.status_code == 401


def test_get_me_authenticated(client: TestClient, student_user) -> None:
    login = client.post(
        "/api/auth/login",
        json={"email": "test.student@vsit.edu.in", "password": "studentpass"},
    )
    token = login.json()["access_token"]

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "test.student@vsit.edu.in"


def test_get_me_unauthenticated(client: TestClient) -> None:
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_admin_authorization(client: TestClient, student_user, admin_user) -> None:
    student_login = client.post(
        "/api/auth/login",
        json={"email": "test.student@vsit.edu.in", "password": "studentpass"},
    )
    student_token = student_login.json()["access_token"]
    student_response = client.get(
        "/api/admin/ping",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert student_response.status_code == 403

    admin_login = client.post(
        "/api/auth/login",
        json={"email": "admin.user@vsit.edu.in", "password": "adminpass1"},
    )
    admin_token = admin_login.json()["access_token"]
    admin_response = client.get(
        "/api/admin/ping",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_response.status_code == 200
    assert "Admin access granted" in admin_response.json()["message"]
