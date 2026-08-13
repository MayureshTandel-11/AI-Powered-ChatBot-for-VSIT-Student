"""Admin ML metrics API tests."""

from pathlib import Path

import pytest

from app.core.config import BACKEND_ROOT
from app.ml.training import train_and_save


@pytest.fixture()
def trained_metrics(tmp_path, monkeypatch):
    model_path = tmp_path / "intent_classifier.joblib"
    metrics_path = tmp_path / "intent_metrics.json"
    train_and_save(
        dataset_path=BACKEND_ROOT / "training" / "intents.csv",
        model_path=model_path,
        metrics_path=metrics_path,
    )
    monkeypatch.setattr("app.services.intent_service.settings.intent_metrics_path", str(metrics_path))
    return metrics_path


def test_ml_metrics_requires_admin(client, student_user, trained_metrics) -> None:
    login = client.post(
        "/api/auth/login",
        json={"email": "test.student@vsit.edu.in", "password": "studentpass"},
    )
    token = login.json()["access_token"]
    response = client.get(
        "/api/admin/ml-metrics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_ml_metrics_returns_trained_values(client, admin_user, trained_metrics) -> None:
    login = client.post(
        "/api/auth/login",
        json={"email": "admin.user@vsit.edu.in", "password": "adminpass1"},
    )
    token = login.json()["access_token"]
    response = client.get(
        "/api/admin/ml-metrics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["model_name"] == "TF-IDF + Logistic Regression"
    assert data["training_examples"] == 288
    assert data["accuracy"] > 0.5
