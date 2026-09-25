"""Tests for intent model training and prediction."""

from pathlib import Path

import pytest

from app.core.config import BACKEND_ROOT
from app.ml.training import load_intent_classifier, load_metrics, train_and_save
from app.services.intent_service import classify_intent, reset_intent_classifier


@pytest.fixture()
def trained_model_paths(tmp_path, monkeypatch):
    model_path = tmp_path / "intent_classifier.joblib"
    metrics_path = tmp_path / "intent_metrics.json"
    dataset_path = BACKEND_ROOT / "training" / "intents.csv"

    monkeypatch.setattr("app.services.intent_service.settings.intent_model_path", str(model_path))
    monkeypatch.setattr("app.services.intent_service.settings.intent_metrics_path", str(metrics_path))

    metrics = train_and_save(
        dataset_path=dataset_path,
        model_path=model_path,
        metrics_path=metrics_path,
    )
    reset_intent_classifier()
    return model_path, metrics_path, metrics


def test_train_and_save_produces_real_metrics(trained_model_paths) -> None:
    _, _, metrics = trained_model_paths
    assert metrics["training_examples"] == 288
    assert 0.0 <= metrics["accuracy"] <= 1.0
    assert 0.0 <= metrics["f1_score"] <= 1.0
    assert "confusion_matrix" in metrics


def test_intent_classifier_predicts_attendance(trained_model_paths) -> None:
    prediction = classify_intent("What is the minimum attendance requirement?")
    assert prediction.intent == "attendance"
    assert prediction.confidence > 0.2


def test_intent_classifier_predicts_general_for_off_topic(trained_model_paths) -> None:
    prediction = classify_intent("Who is the current president of the United States?")
    assert prediction.intent == "general"


def test_saved_model_can_be_reloaded(trained_model_paths) -> None:
    model_path, metrics_path, _ = trained_model_paths
    classifier = load_intent_classifier(model_path)
    metrics = load_metrics(metrics_path)
    result = classifier.predict("When are semester exams?")
    assert result.intent == "examination"
    assert metrics is not None


def test_intent_confidence_threshold(tmp_path, monkeypatch) -> None:
    from app.services.intent_service import predict_intent_with_confidence, reset_intent_classifier

    model_path = tmp_path / "intent_classifier.joblib"
    metrics_path = tmp_path / "intent_metrics.json"
    train_and_save(model_path=model_path, metrics_path=metrics_path)
    monkeypatch.setattr("app.services.intent_service.settings.intent_model_path", str(model_path))
    monkeypatch.setattr("app.services.intent_service.settings.intent_confidence_threshold", 0.99)

    reset_intent_classifier()
    result = predict_intent_with_confidence("What is the minimum attendance requirement?")
    assert result["raw_intent"] == "attendance"
    assert result["intent"] == "unknown"
    reset_intent_classifier()
