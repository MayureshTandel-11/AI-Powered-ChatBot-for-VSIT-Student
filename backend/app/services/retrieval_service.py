"""FAISS vector store with hybrid semantic + keyword retrieval."""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import faiss
import numpy as np
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Document, DocumentChunk
from app.services.embedding_service import get_embedding_service
from app.services.query_service import infer_category_from_filename

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class RetrievedChunk:
    chunk_db_id: int
    document_id: int
    chunk_id: int
    content: str
    source: str
    page_number: int | None
    score: float
    filename: str
    section: str | None = None
    category: str | None = None


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2}


def _keyword_overlap_score(query: str, content: str) -> float:
    query_tokens = _tokenize(query)
    if not query_tokens:
        return 0.0
    content_tokens = _tokenize(content)
    if not content_tokens:
        return 0.0
    overlap = len(query_tokens & content_tokens)
    return overlap / len(query_tokens)


def _extract_section_from_content(content: str) -> str | None:
    """Infer a section heading from chunk content."""
    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.isupper() and 4 <= len(stripped) <= 80:
            return stripped.title()
        if re.match(r"^\d+\.\s+[A-Z]", stripped):
            return stripped
        break
    return None


class VectorStore:
    """Cosine-similarity search using FAISS IndexFlatIP on normalized vectors."""

    def __init__(self) -> None:
        self.embedding_service = get_embedding_service()
        self.dimension = self.embedding_service.dimension
        self.index: faiss.IndexFlatIP = faiss.IndexFlatIP(self.dimension)
        self.metadata: list[dict] = []
        self.store_dir = Path(settings.vector_store_directory)
        self.index_path = self.store_dir / "faiss.index"
        self.metadata_path = self.store_dir / "metadata.json"

    def load(self) -> None:
        self.store_dir.mkdir(parents=True, exist_ok=True)
        if self.index_path.exists() and self.metadata_path.exists():
            self.index = faiss.read_index(str(self.index_path))
            self.metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            logger.info("Loaded FAISS index with %s vectors", self.index.ntotal)
        else:
            self.index = faiss.IndexFlatIP(self.dimension)
            self.metadata = []
            logger.info("Initialized empty FAISS index")

    def save(self) -> None:
        self.store_dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(self.index_path))
        self.metadata_path.write_text(json.dumps(self.metadata, indent=2), encoding="utf-8")
        logger.info("Saved FAISS index with %s vectors", self.index.ntotal)

    def clear(self) -> None:
        self.index = faiss.IndexFlatIP(self.dimension)
        self.metadata = []

    def rebuild_from_database(self, db: Session) -> int:
        """Rebuild the entire index from processed document chunks."""
        self.clear()
        chunks = (
            db.query(DocumentChunk, Document)
            .join(Document, DocumentChunk.document_id == Document.id)
            .filter(Document.status == "processed")
            .order_by(DocumentChunk.id.asc())
            .all()
        )
        if not chunks:
            self.save()
            return 0

        texts = [chunk.content for chunk, _ in chunks]
        vectors = self.embedding_service.embed_texts(texts)
        self.index.add(vectors)

        self.metadata = []
        for faiss_id, (chunk, document) in enumerate(chunks):
            category = infer_category_from_filename(document.filename)
            section = _extract_section_from_content(chunk.content)
            self.metadata.append(
                {
                    "faiss_id": faiss_id,
                    "chunk_db_id": chunk.id,
                    "document_id": document.id,
                    "chunk_id": chunk.chunk_id,
                    "filename": document.filename,
                    "source": chunk.source,
                    "page_number": chunk.page_number,
                    "content": chunk.content,
                    "section": section,
                    "category": category,
                }
            )

        self.save()
        logger.info("Rebuilt vector index with %s chunks", len(self.metadata))
        return len(self.metadata)

    def index_document(self, db: Session, document_id: int) -> int:
        """Add all chunks for one document by rebuilding the index."""
        document = db.query(Document).filter(Document.id == document_id).first()
        if document is None or document.status != "processed":
            return 0
        return self.rebuild_from_database(db)

    def _semantic_search(self, query: str, k: int) -> list[tuple[dict, float]]:
        if self.index.ntotal == 0:
            return []

        k = min(k, self.index.ntotal)
        query_vector = self.embedding_service.embed_query(query).reshape(1, -1)
        scores, indices = self.index.search(query_vector, k)

        results: list[tuple[dict, float]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
            results.append((self.metadata[idx], float(score)))
        return results

    def _combine_score(
        self,
        semantic_score: float,
        keyword_score: float,
        category: str | None,
        intent_hint: str | None,
    ) -> float:
        keyword_weight = settings.hybrid_keyword_weight
        combined = (semantic_score * (1.0 - keyword_weight)) + (keyword_score * keyword_weight)

        if (
            intent_hint
            and intent_hint not in {"general", "unknown"}
            and category
            and category == intent_hint
        ):
            combined += settings.intent_category_boost

        return min(combined, 1.0)

    def _meta_to_chunk(self, meta: dict, score: float) -> RetrievedChunk:
        return RetrievedChunk(
            chunk_db_id=meta["chunk_db_id"],
            document_id=meta["document_id"],
            chunk_id=meta["chunk_id"],
            content=meta["content"],
            source=meta["source"],
            page_number=meta.get("page_number"),
            score=score,
            filename=meta["filename"],
            section=meta.get("section"),
            category=meta.get("category"),
        )

    def search(
        self,
        query: str,
        *,
        top_k: int | None = None,
        expanded_queries: list[str] | None = None,
        intent_hint: str | None = None,
        is_broad: bool = False,
    ) -> list[RetrievedChunk]:
        """Hybrid retrieval using semantic similarity, keyword overlap, and intent hints."""
        if self.index.ntotal == 0:
            return []

        k = top_k or (settings.broad_query_top_k if is_broad else settings.top_k)
        search_k = min(max(k * 2, k), self.index.ntotal)

        queries = [query]
        if expanded_queries:
            queries.extend(q for q in expanded_queries if q and q not in queries)

        best_by_chunk: dict[int, RetrievedChunk] = {}

        for sub_query in queries:
            for meta, semantic_score in self._semantic_search(sub_query, search_k):
                keyword_score = _keyword_overlap_score(query, meta["content"])
                final_score = self._combine_score(
                    semantic_score,
                    keyword_score,
                    meta.get("category"),
                    intent_hint,
                )

                chunk_id = meta["chunk_db_id"]
                existing = best_by_chunk.get(chunk_id)
                if existing is None or final_score > existing.score:
                    best_by_chunk[chunk_id] = self._meta_to_chunk(meta, final_score)

        ranked = sorted(best_by_chunk.values(), key=lambda item: item.score, reverse=True)

        filtered = [chunk for chunk in ranked if chunk.score >= settings.similarity_threshold]

        if not filtered and ranked:
            # Keep the best match if it is reasonably close to the threshold.
            if ranked[0].score >= settings.similarity_threshold - 0.08:
                filtered = [ranked[0]]

        if is_broad:
            return self._diversify_broad_results(filtered[:k])
        return filtered[:k]

    def _diversify_broad_results(self, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        """Prefer diverse source documents for broad overview questions."""
        if not chunks:
            return []

        selected: list[RetrievedChunk] = []
        seen_documents: set[int] = set()

        for chunk in chunks:
            if chunk.document_id in seen_documents:
                continue
            selected.append(chunk)
            seen_documents.add(chunk.document_id)

        for chunk in chunks:
            if chunk in selected:
                continue
            selected.append(chunk)

        return selected

    def is_available(self) -> bool:
        return self.index.ntotal > 0


_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
        _vector_store.load()
    return _vector_store


def reset_vector_store() -> None:
    global _vector_store
    _vector_store = None
