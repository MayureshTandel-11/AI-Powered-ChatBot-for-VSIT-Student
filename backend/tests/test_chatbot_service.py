"""Unit tests for chatbot helper logic."""

from app.services.chatbot_service import (
    OFF_TOPIC_ANSWER,
    _build_sources,
    _is_greeting,
    _is_off_topic,
)
from app.services.retrieval_service import RetrievedChunk


def test_is_off_topic_detects_non_college_question() -> None:
    assert _is_off_topic("Who is the current president of the United States?")


def test_is_off_topic_detects_geography_question() -> None:
    assert _is_off_topic("What is the capital of France?")


def test_is_greeting_detects_hello() -> None:
    assert _is_greeting("Hello")


def test_build_sources_deduplicates_documents() -> None:
    chunks = [
        RetrievedChunk(
            chunk_db_id=1,
            document_id=1,
            chunk_id=0,
            content="Attendance policy text",
            source="attendance_policy.txt",
            page_number=1,
            score=0.9,
            filename="attendance_policy.txt",
        ),
        RetrievedChunk(
            chunk_db_id=2,
            document_id=1,
            chunk_id=1,
            content="More attendance text",
            source="attendance_policy.txt",
            page_number=1,
            score=0.8,
            filename="attendance_policy.txt",
        ),
    ]
    sources = _build_sources(chunks)
    assert len(sources) == 1
    assert sources[0].document == "attendance_policy.txt"
    assert sources[0].page == 1


def test_off_topic_answer_is_safe() -> None:
    assert "college" in OFF_TOPIC_ANSWER.lower()
