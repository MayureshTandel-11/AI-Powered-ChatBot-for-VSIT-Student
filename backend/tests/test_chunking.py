"""Tests for paragraph-aware chunking."""

from app.services.chunking_service import chunk_pages


def test_chunk_pages_respects_paragraphs() -> None:
    text = "Paragraph one about attendance.\n\nParagraph two about examinations."
    chunks = chunk_pages([(text, 1)], source="policy.txt", chunk_size=20, chunk_overlap=5)
    assert chunks
    assert all(chunk.source == "policy.txt" for chunk in chunks)
    assert chunks[0].page_number == 1


def test_chunk_pages_splits_long_content() -> None:
    words = " ".join(f"word{i}" for i in range(1200))
    chunks = chunk_pages([(words, None)], source="long.txt", chunk_size=500, chunk_overlap=50)
    assert len(chunks) >= 2
    assert chunks[0].chunk_id == 0
    assert chunks[1].chunk_id == 1
