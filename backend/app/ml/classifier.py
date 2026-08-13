"""Intent classification model wrapper."""

from dataclasses import dataclass

from app.ml.preprocessing import preprocess_text


@dataclass
class IntentPrediction:
    intent: str
    confidence: float


class IntentClassifier:
    """TF-IDF + Logistic Regression intent classifier."""

    def __init__(self, vectorizer, classifier, labels: list[str]) -> None:
        self.vectorizer = vectorizer
        self.classifier = classifier
        self.labels = labels

    def predict(self, question: str) -> IntentPrediction:
        cleaned = preprocess_text(question)
        if not cleaned:
            return IntentPrediction(intent="general", confidence=0.0)

        features = self.vectorizer.transform([cleaned])
        probabilities = self.classifier.predict_proba(features)[0]
        best_index = int(probabilities.argmax())
        return IntentPrediction(
            intent=self.labels[best_index],
            confidence=float(probabilities[best_index]),
        )

    def predict_batch(self, questions: list[str]) -> list[IntentPrediction]:
        return [self.predict(question) for question in questions]
