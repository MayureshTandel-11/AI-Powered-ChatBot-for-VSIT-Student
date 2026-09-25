"""Unit tests for chatbot helper logic."""

from app.services.chatbot_service import _build_sources
from app.services.query_service import OFF_TOPIC_RESPONSE, match_conversational
from app.services.retrieval_service import RetrievedChunk


def test_match_conversational_detects_off_topic() -> None:
    match = match_conversational("Who is the current president of the United States?")
    assert match is not None
    assert match.kind == "off_topic"


def test_match_conversational_detects_geography_question() -> None:
    match = match_conversational("What is the capital of France?")
    assert match is not None
    assert match.kind == "off_topic"


def test_match_conversational_detects_greeting() -> None:
    match = match_conversational("Hello")
    assert match is not None
    assert match.kind == "greeting"


def test_build_sources_deduplicates_documents() -> None:
    chunks = [
        RetrievedChunk(
            chunk_db_id=1,
            document_id=1,
            chunk_id=0,
            content="Attendance policy text",
            source="attendance_management.txt",
            page_number=1,
            score=0.9,
            filename="attendance_management.txt",
        ),
        RetrievedChunk(
            chunk_db_id=2,
            document_id=1,
            chunk_id=1,
            content="More attendance text",
            source="attendance_management.txt",
            page_number=1,
            score=0.8,
            filename="attendance_management.txt",
        ),
    ]
    sources = _build_sources(chunks)
    assert len(sources) == 1
    assert sources[0].document == "attendance_management.txt"
    assert sources[0].page == 1


def test_off_topic_response_is_safe() -> None:
    assert "college" in OFF_TOPIC_RESPONSE.lower()
