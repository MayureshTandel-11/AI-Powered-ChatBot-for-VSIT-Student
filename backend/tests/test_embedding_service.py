"""Tests for embedding service."""

import numpy as np

from app.services.embedding_service import EmbeddingService, FakeEmbeddingBackend


def test_fake_embedding_returns_normalized_vectors() -> None:
    service = EmbeddingService(backend=FakeEmbeddingBackend())
    vectors = service.embed_texts(["attendance policy for students"])
    assert vectors.shape == (1, 384)
    norm = np.linalg.norm(vectors[0])
    assert abs(norm - 1.0) < 1e-5


def test_similar_texts_have_higher_similarity() -> None:
    service = EmbeddingService(backend=FakeEmbeddingBackend())
    query = service.embed_query("attendance requirement for students")
    doc = service.embed_query("students must maintain attendance in each subject")
    unrelated = service.embed_query("library book borrowing limits")

    query_doc_similarity = float(np.dot(query, doc))
    query_unrelated_similarity = float(np.dot(query, unrelated))
    assert query_doc_similarity > query_unrelated_similarity
