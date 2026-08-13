"""Admin statistics API tests."""


def test_statistics_requires_admin(client, student_user) -> None:
    login = client.post(
        "/api/auth/login",
        json={"email": "test.student@vsit.edu.in", "password": "studentpass"},
    )
    token = login.json()["access_token"]
    response = client.get(
        "/api/admin/statistics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_statistics_returns_counts(client, admin_user, student_user) -> None:
    login = client.post(
        "/api/auth/login",
        json={"email": "admin.user@vsit.edu.in", "password": "adminpass1"},
    )
    token = login.json()["access_token"]
    response = client.get(
        "/api/admin/statistics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_students"] >= 1
    assert "total_documents" in data
    assert "total_questions" in data
    assert "active_users" in data
