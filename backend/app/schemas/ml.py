"""Schemas for ML model metrics."""

from pydantic import BaseModel


class MLMetricsResponse(BaseModel):
    model_name: str
    training_examples: int
    test_examples: int | None = None
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    trained: bool = True
