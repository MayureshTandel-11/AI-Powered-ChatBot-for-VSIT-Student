"""RAG evaluation tests for natural-language query handling."""

from pathlib import Path

import pytest

from app.core.config import BACKEND_ROOT
from app.db.models import Document, DocumentChunk
from app.ml.training import train_and_save
from app.services.intent_service import predict_intent_with_confidence, reset_intent_classifier
from app.services.query_service import detect_broad_query, match_conversational, process_query
from app.services.retrieval_service import VectorStore, get_vector_store

SAMPLES_DIR = BACKEND_ROOT / "data" / "documents" / "samples"

LIBRARY_QUESTIONS = [
    "What are the library timings?",
    "Tell me about the library.",
    "Can you explain the library services?",
    "What facilities does the library have?",
    "Where can students borrow books?",
    "How does the library work?",
    "I want information about the library.",
]

ATTENDANCE_QUESTIONS = [
    "What is the attendance requirement?",
    "How much attendance do I need?",
    "Can you explain the attendance rules?",
    "Will low attendance affect my exams?",
]

EXAM_QUESTIONS = [
    "When are the semester exams?",
    "Tell me about the exams.",
    "How does the examination process work?",
]


@pytest.fixture()
def trained_intent_model(tmp_path, monkeypatch):
    model_path = tmp_path / "intent_classifier.joblib"
    metrics_path = tmp_path / "intent_metrics.json"
    train_and_save(model_path=model_path, metrics_path=metrics_path)
    monkeypatch.setattr("app.services.intent_service.settings.intent_model_path", str(model_path))
    monkeypatch.setattr("app.services.intent_service.settings.intent_metrics_path", str(metrics_path))
    reset_intent_classifier()
    yield
    reset_intent_classifier()


def _seed_document(db_session, filename: str) -> None:
    text = (SAMPLES_DIR / filename).read_text(encoding="utf-8")
    document = Document(
        filename=filename,
        file_path=str(SAMPLES_DIR / filename),
        document_type="txt",
        status="processed",
        chunk_count=1,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    chunk = DocumentChunk(
        document_id=document.id,
        chunk_id=0,
        content=text,
        page_number=1,
        source=document.filename,
        word_count=len(text.split()),
    )
    db_session.add(chunk)
    db_session.commit()


def _seed_knowledge_base(db_session) -> None:
    for filename in (
        "library_management.txt",
        "readingroom.txt",
        "attendance_management.txt",
        "examination_evaluation.txt",
    ):
        _seed_document(db_session, filename)
    get_vector_store().rebuild_from_database(db_session)


def _top_content_has_keyword(results, keyword: str) -> bool:
    if not results:
        return False
    combined = " ".join(result.content.lower() for result in results)
    filename_match = any(keyword in result.filename.lower() for result in results)
    return keyword in combined or filename_match


def _evaluate_retrieval(store: VectorStore, questions: list[str], keyword: str) -> dict[str, bool]:
    outcomes: dict[str, bool] = {}
    for question in questions:
        processed = process_query(question, intent_hint=keyword)
        results = store.search(
            processed.retrieval_query,
            expanded_queries=processed.expanded_queries,
            intent_hint=keyword,
            is_broad=processed.is_broad,
        )
        outcomes[question] = _top_content_has_keyword(results, keyword)
    return outcomes


def test_greeting_skips_retrieval() -> None:
    match = match_conversational("Hi")
    assert match is not None
    assert match.kind == "greeting"


def test_broad_query_detection_for_library_phrases() -> None:
    assert detect_broad_query("Tell me about library service.")
    assert detect_broad_query("Can you explain what facilities our library provides?")


def test_intent_confidence_does_not_block_unknown(trained_intent_model) -> None:
    result = predict_intent_with_confidence("Hey there, random wording about stuff")
    assert "confidence" in result
    assert result["intent"] in {"unknown", "general", result["raw_intent"]}


def test_library_natural_language_retrieval(db_session) -> None:
    _seed_knowledge_base(db_session)
    store = VectorStore()
    store.load()

    outcomes = _evaluate_retrieval(store, LIBRARY_QUESTIONS, "library")
    success_count = sum(outcomes.values())
    success_rate = success_count / len(LIBRARY_QUESTIONS)

    assert success_count >= 5, f"Library retrieval outcomes: {outcomes}"
    assert success_rate >= 0.7


def test_attendance_natural_language_retrieval(db_session) -> None:
    _seed_knowledge_base(db_session)
    store = VectorStore()
    store.load()

    outcomes = _evaluate_retrieval(store, ATTENDANCE_QUESTIONS, "attendance")
    assert sum(outcomes.values()) >= 3, f"Attendance retrieval outcomes: {outcomes}"


def test_examination_natural_language_retrieval(db_session) -> None:
    _seed_knowledge_base(db_session)
    store = VectorStore()
    store.load()

    outcomes = _evaluate_retrieval(store, EXAM_QUESTIONS, "examination")
    assert sum(outcomes.values()) >= 2, f"Exam retrieval outcomes: {outcomes}"


def test_follow_up_library_borrowing_query(db_session) -> None:
    _seed_knowledge_base(db_session)
    store = VectorStore()
    store.load()

    history = [
        ("user", "Tell me about the library."),
        ("assistant", "The library provides books, computers, and an e-library."),
    ]
    processed = process_query(
        "How many books can I borrow?",
        history=history,
        intent_hint="library",
    )
    results = store.search(
        processed.retrieval_query,
        expanded_queries=processed.expanded_queries,
        intent_hint="library",
        is_broad=processed.is_broad,
    )
    assert results
    assert _top_content_has_keyword(results, "library") or _top_content_has_keyword(results, "book")


def test_unknown_topic_returns_no_results(db_session) -> None:
    _seed_knowledge_base(db_session)
    store = VectorStore()
    store.load()

    processed = process_query(
        "Tell me about a college policy that isn't in the uploaded documents.",
        intent_hint=None,
    )
    results = store.search(
        processed.retrieval_query,
        expanded_queries=processed.expanded_queries,
        intent_hint=None,
        is_broad=processed.is_broad,
    )
    # Either no results or very weak matches only — should not strongly match a seeded topic.
    if results:
        assert results[0].score < 0.6


def test_rag_evaluation_report(db_session, capsys) -> None:
    """Print a small retrieval evaluation report for manual inspection."""
    _seed_knowledge_base(db_session)
    store = VectorStore()
    store.load()

    sections = {
        "library": LIBRARY_QUESTIONS,
        "attendance": ATTENDANCE_QUESTIONS,
        "examination": EXAM_QUESTIONS,
    }

    print("\n=== RAG Evaluation Report ===")
    for label, questions in sections.items():
        outcomes = _evaluate_retrieval(store, questions, label)
        total = len(outcomes)
        success = sum(outcomes.values())
        print(f"{label}: {success}/{total} retrieval hits ({success / total:.0%})")
        for question, hit in outcomes.items():
            print(f"  [{'PASS' if hit else 'FAIL'}] {question}")

    captured = capsys.readouterr()
    assert "RAG Evaluation Report" in captured.out
