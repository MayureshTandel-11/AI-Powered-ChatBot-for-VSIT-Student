"""FAISS vector store with persistent metadata mapping."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import faiss
import numpy as np
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Document, DocumentChunk
from app.services.embedding_service import get_embedding_service

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

    def search(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        if self.index.ntotal == 0:
            return []

        k = top_k or settings.top_k
        k = min(k, self.index.ntotal)
        query_vector = self.embedding_service.embed_query(query).reshape(1, -1)
        scores, indices = self.index.search(query_vector, k)

        results: list[RetrievedChunk] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
            if float(score) < settings.similarity_threshold:
                continue
            meta = self.metadata[idx]
            results.append(
                RetrievedChunk(
                    chunk_db_id=meta["chunk_db_id"],
                    document_id=meta["document_id"],
                    chunk_id=meta["chunk_id"],
                    content=meta["content"],
                    source=meta["source"],
                    page_number=meta.get("page_number"),
                    score=float(score),
                    filename=meta["filename"],
                )
            )
        return results

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
