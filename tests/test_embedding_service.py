from __future__ import annotations

import pytest

from app.config.settings import Settings
from app.services.embedding_service import EmbeddingService


def test_parse_single_embedding():
    vectors = EmbeddingService._parse_embeddings({"data": {"embedding": [0.1, 0.2, 0.3]}})
    assert vectors == [[0.1, 0.2, 0.3]]


def test_parse_list_embeddings():
    vectors = EmbeddingService._parse_embeddings(
        {"data": [{"embedding": [0.1]}, {"embedding": [0.2, 0.3]}]}
    )
    assert vectors == [[0.1], [0.2, 0.3]]


def test_parse_invalid_response():
    with pytest.raises(ValueError, match="unexpected embedding API response"):
        EmbeddingService._parse_embeddings({"data": {}})


def test_rejects_uuid_like_api_key():
    settings = Settings(embedding_api_key="sk-a396a7c4-9928-4195-8120-ec954099d60e")
    service = EmbeddingService(settings)
    with pytest.raises(ValueError, match="不是火山方舟有效 Key"):
        service.embed(input_items=[{"type": "text", "text": "hi"}])
