"""Reusable text chunking with paragraph-aware splitting."""

import re
from dataclasses import dataclass

from app.core.config import get_settings
from app.utils.text_processing import clean_text, count_words

settings = get_settings()


@dataclass
class TextChunk:
    chunk_id: int
    content: str
    page_number: int | None
    source: str
    word_count: int
    section: str | None = None


def _detect_section_heading(text: str) -> str | None:
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.isupper() and 4 <= len(stripped) <= 80:
            return stripped.title()
        if re.match(r"^\d+\.\s+[A-Z]", stripped):
            return stripped
        break
    return None


def chunk_pages(
    pages: list[tuple[str, int | None]],
    *,
    source: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[TextChunk]:
    """Split document pages into overlapping word-based chunks."""
    size = chunk_size or settings.chunk_size
    overlap = chunk_overlap or settings.chunk_overlap
    if overlap >= size:
        overlap = max(0, size // 5)

    chunks: list[TextChunk] = []
    chunk_index = 0
    current_section: str | None = None

    for page_text, page_number in pages:
        cleaned_page = clean_text(page_text)
        if not cleaned_page:
            continue

        paragraphs = [part.strip() for part in cleaned_page.split("\n\n") if part.strip()]
        buffer = ""

        for paragraph in paragraphs:
            heading = _detect_section_heading(paragraph)
            if heading:
                current_section = heading

            candidate = f"{buffer}\n\n{paragraph}".strip() if buffer else paragraph
            if count_words(candidate) <= size:
                buffer = candidate
                continue

            if buffer:
                chunks.extend(
                    _split_text_block(
                        buffer,
                        source=source,
                        page_number=page_number,
                        chunk_size=size,
                        chunk_overlap=overlap,
                        start_index=chunk_index,
                        section=current_section,
                    )
                )
                chunk_index = chunks[-1].chunk_id + 1 if chunks else 0
                buffer = paragraph
            else:
                chunks.extend(
                    _split_text_block(
                        paragraph,
                        source=source,
                        page_number=page_number,
                        chunk_size=size,
                        chunk_overlap=overlap,
                        start_index=chunk_index,
                        section=current_section,
                    )
                )
                chunk_index = chunks[-1].chunk_id + 1 if chunks else 0
                buffer = ""

        if buffer:
            chunks.extend(
                _split_text_block(
                    buffer,
                    source=source,
                    page_number=page_number,
                    chunk_size=size,
                    chunk_overlap=overlap,
                    start_index=chunk_index,
                    section=current_section,
                )
            )
            chunk_index = chunks[-1].chunk_id + 1 if chunks else 0

    return chunks


def _split_text_block(
    text: str,
    *,
    source: str,
    page_number: int | None,
    chunk_size: int,
    chunk_overlap: int,
    start_index: int,
    section: str | None = None,
) -> list[TextChunk]:
    words = text.split()
    if not words:
        return []

    if len(words) <= chunk_size:
        content = " ".join(words)
        return [
            TextChunk(
                chunk_id=start_index,
                content=content,
                page_number=page_number,
                source=source,
                word_count=count_words(content),
                section=section,
            )
        ]

    chunks: list[TextChunk] = []
    step = max(1, chunk_size - chunk_overlap)
    index = start_index

    for start in range(0, len(words), step):
        window = words[start : start + chunk_size]
        if not window:
            break
        content = " ".join(window)
        chunks.append(
            TextChunk(
                chunk_id=index,
                content=content,
                page_number=page_number,
                source=source,
                word_count=count_words(content),
                section=section,
            )
        )
        index += 1
        if start + chunk_size >= len(words):
            break

    return chunks
