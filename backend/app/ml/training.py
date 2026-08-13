"""Train, evaluate, and persist the intent classification model."""

import json
import logging
from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split

from app.core.config import BACKEND_ROOT
from app.ml.classifier import IntentClassifier
from app.ml.preprocessing import preprocess_text

logger = logging.getLogger(__name__)

DEFAULT_INTENTS_PATH = BACKEND_ROOT / "training" / "intents.csv"
DEFAULT_MODEL_PATH = BACKEND_ROOT / "data" / "models" / "intent_classifier.joblib"
DEFAULT_METRICS_PATH = BACKEND_ROOT / "data" / "models" / "intent_metrics.json"


def load_intent_dataset(path: Path | None = None) -> pd.DataFrame:
    dataset_path = path or DEFAULT_INTENTS_PATH
    frame = pd.read_csv(dataset_path)
    if "question" not in frame.columns or "intent" not in frame.columns:
        raise ValueError("intents.csv must contain 'question' and 'intent' columns")

    frame = frame.dropna(subset=["question", "intent"]).copy()
    frame["question"] = frame["question"].astype(str).map(preprocess_text)
    frame["intent"] = frame["intent"].astype(str).str.strip().str.lower()
    frame = frame[frame["question"] != ""]
    return frame


def train_intent_classifier(
    dataset_path: Path | None = None,
    test_size: float = 0.2,
    random_state: int = 42,
) -> tuple[IntentClassifier, dict]:
    frame = load_intent_dataset(dataset_path)
    if frame["intent"].nunique() < 2:
        raise ValueError("Dataset must contain at least two intent classes")

    x_train, x_test, y_train, y_test = train_test_split(
        frame["question"],
        frame["intent"],
        test_size=test_size,
        random_state=random_state,
        stratify=frame["intent"],
    )

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        min_df=1,
        max_df=0.95,
        sublinear_tf=True,
    )
    x_train_vectors = vectorizer.fit_transform(x_train)
    x_test_vectors = vectorizer.transform(x_test)

    classifier = LogisticRegression(max_iter=1000, random_state=random_state)
    classifier.fit(x_train_vectors, y_train)

    labels = sorted(frame["intent"].unique())
    model = IntentClassifier(vectorizer=vectorizer, classifier=classifier, labels=labels)

    predictions = classifier.predict(x_test_vectors)
    metrics = {
        "model_name": "TF-IDF + Logistic Regression",
        "training_examples": int(len(frame)),
        "test_examples": int(len(y_test)),
        "accuracy": float(accuracy_score(y_test, predictions)),
        "precision": float(precision_score(y_test, predictions, average="weighted", zero_division=0)),
        "recall": float(recall_score(y_test, predictions, average="weighted", zero_division=0)),
        "f1_score": float(f1_score(y_test, predictions, average="weighted", zero_division=0)),
        "confusion_matrix": {
            "labels": labels,
            "matrix": confusion_matrix(y_test, predictions, labels=labels).tolist(),
        },
        "classification_report": classification_report(
            y_test,
            predictions,
            labels=labels,
            zero_division=0,
            output_dict=True,
        ),
    }

    logger.info(
        "Intent model trained | examples=%s accuracy=%.3f f1=%.3f",
        metrics["training_examples"],
        metrics["accuracy"],
        metrics["f1_score"],
    )
    return model, metrics


def save_artifacts(
    model: IntentClassifier,
    metrics: dict,
    model_path: Path | None = None,
    metrics_path: Path | None = None,
) -> tuple[Path, Path]:
    resolved_model_path = model_path or DEFAULT_MODEL_PATH
    resolved_metrics_path = metrics_path or DEFAULT_METRICS_PATH
    resolved_model_path.parent.mkdir(parents=True, exist_ok=True)

    artifact = {
        "vectorizer": model.vectorizer,
        "classifier": model.classifier,
        "labels": model.labels,
    }
    joblib.dump(artifact, resolved_model_path)
    resolved_metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return resolved_model_path, resolved_metrics_path


def load_intent_classifier(model_path: Path | None = None) -> IntentClassifier:
    resolved_model_path = model_path or DEFAULT_MODEL_PATH
    if not resolved_model_path.exists():
        raise FileNotFoundError(f"Intent model not found at {resolved_model_path}")

    artifact = joblib.load(resolved_model_path)
    return IntentClassifier(
        vectorizer=artifact["vectorizer"],
        classifier=artifact["classifier"],
        labels=artifact["labels"],
    )


def load_metrics(metrics_path: Path | None = None) -> dict | None:
    resolved_metrics_path = metrics_path or DEFAULT_METRICS_PATH
    if not resolved_metrics_path.exists():
        return None
    return json.loads(resolved_metrics_path.read_text(encoding="utf-8"))


def train_and_save(
    dataset_path: Path | None = None,
    model_path: Path | None = None,
    metrics_path: Path | None = None,
) -> dict:
    model, metrics = train_intent_classifier(dataset_path=dataset_path)
    save_artifacts(model, metrics, model_path=model_path, metrics_path=metrics_path)
    return metrics
