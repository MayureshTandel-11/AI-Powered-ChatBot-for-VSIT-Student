"""Sentence-transformer embedding generation with singleton model loading."""

import logging
from typing import Protocol

import numpy as np

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class EmbeddingBackend(Protocol):
    def encode(self, texts: list[str], normalize_embeddings: bool = True) -> np.ndarray: ...


class SentenceTransformerBackend:
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        logger.info("Loading embedding model: %s", model_name)
        self._model = SentenceTransformer(model_name)
        if hasattr(self._model, "get_embedding_dimension"):
            self.dimension = int(self._model.get_embedding_dimension())
        else:
            self.dimension = int(self._model.get_sentence_embedding_dimension())

    def encode(self, texts: list[str], normalize_embeddings: bool = True) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)
        vectors = self._model.encode(
            texts,
            normalize_embeddings=normalize_embeddings,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return np.asarray(vectors, dtype=np.float32)


class FakeEmbeddingBackend:
    """Deterministic lightweight backend for unit tests (no model download)."""

    dimension = 384

    def encode(self, texts: list[str], normalize_embeddings: bool = True) -> np.ndarray:
        vectors = np.zeros((len(texts), self.dimension), dtype=np.float32)
        for row, text in enumerate(texts):
            for token in text.lower().split():
                index = hash(token) % self.dimension
                vectors[row, index] += 1.0
            norm = np.linalg.norm(vectors[row])
            if normalize_embeddings and norm > 0:
                vectors[row] /= norm
        return vectors


class EmbeddingService:
    def __init__(self, backend: EmbeddingBackend | None = None) -> None:
        self._backend = backend or self._create_default_backend()

    @property
    def dimension(self) -> int:
        return int(self._backend.dimension)

    def _create_default_backend(self) -> EmbeddingBackend:
        if settings.use_fake_embeddings:
            return FakeEmbeddingBackend()
        return SentenceTransformerBackend(settings.embedding_model)

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        return self._backend.encode(texts, normalize_embeddings=True)

    def embed_query(self, query: str) -> np.ndarray:
        vectors = self.embed_texts([query])
        return vectors[0]


_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


def reset_embedding_service() -> None:
    global _embedding_service
    _embedding_service = None
