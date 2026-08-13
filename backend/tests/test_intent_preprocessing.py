"""Tests for intent text preprocessing."""

from app.ml.preprocessing import preprocess_text


def test_preprocess_text_lowercases_and_strips() -> None:
    assert preprocess_text("  What IS the Attendance?  ") == "what is the attendance?"


def test_preprocess_text_removes_punctuation() -> None:
    assert preprocess_text("Hello, student!") == "hello student"
