"""Tests for text cleaning utilities."""

from app.utils.text_processing import clean_text, count_words


def test_clean_text_normalizes_whitespace() -> None:
    raw = "Attendance   policy\r\n\r\n\n\nStudents   must   follow rules."
    cleaned = clean_text(raw)
    assert "  " not in cleaned
    assert cleaned.count("\n\n") == 1


def test_count_words() -> None:
    assert count_words("one two three") == 3
    assert count_words("") == 0
