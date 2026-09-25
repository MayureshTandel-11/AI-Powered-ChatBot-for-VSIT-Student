"""Tests for query preprocessing and broad-query detection."""

from app.services.query_service import (
    detect_broad_query,
    expand_query,
    normalize_query,
    process_query,
    rewrite_follow_up_query,
)


def test_normalize_query_fixes_common_library_typo() -> None:
    assert "library" in normalize_query("Tell me about the libary").lower()


def test_detect_broad_query_for_conversational_phrasing() -> None:
    assert detect_broad_query("Tell me about the library")
    assert detect_broad_query("Can you explain the attendance rules?")


def test_detect_broad_query_false_for_specific_question() -> None:
    assert not detect_broad_query("What are the library timings on Monday?")


def test_expand_query_adds_intent_terms() -> None:
    expansions = expand_query("Tell me about services", "library")
    assert expansions
    assert any("library" in term for term in expansions)


def test_rewrite_follow_up_adds_library_context() -> None:
    history = [
        ("user", "Tell me about the library."),
        ("assistant", "The library provides books and digital resources."),
    ]
    rewritten = rewrite_follow_up_query("How many books can I borrow?", history, "library")
    assert "library" in rewritten.lower()
    assert "borrow" in rewritten.lower()


def test_process_query_marks_broad_library_question() -> None:
    processed = process_query("Tell me about library service.", intent_hint="library")
    assert processed.is_broad
    assert processed.retrieval_query
    assert processed.expanded_queries
