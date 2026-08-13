"""Runtime intent classification service."""

import logging
from pathlib import Path

from app.core.config import BACKEND_ROOT, get_settings
from app.ml.classifier import IntentClassifier, IntentPrediction
from app.ml.training import load_intent_classifier, load_metrics

logger = logging.getLogger(__name__)
settings = get_settings()

DEFAULT_MODEL_PATH = BACKEND_ROOT / "data" / "models" / "intent_classifier.joblib"
DEFAULT_METRICS_PATH = BACKEND_ROOT / "data" / "models" / "intent_metrics.json"

_intent_classifier: IntentClassifier | None = None


class IntentServiceError(Exception):
    pass


def get_intent_classifier() -> IntentClassifier:
    global _intent_classifier
    if _intent_classifier is None:
        model_path = Path(settings.intent_model_path)
        if not model_path.exists():
            raise IntentServiceError(
                "Intent classification model is not trained. "
                "Run: python -m app.ml.train_model"
            )
        _intent_classifier = load_intent_classifier(model_path)
        logger.info("Loaded intent classifier from %s", model_path)
    return _intent_classifier


def classify_intent(question: str) -> IntentPrediction:
    classifier = get_intent_classifier()
    return classifier.predict(question)


def get_intent_metrics() -> dict | None:
    metrics_path = Path(settings.intent_metrics_path)
    return load_metrics(metrics_path)


def reset_intent_classifier() -> None:
    global _intent_classifier
    _intent_classifier = None
