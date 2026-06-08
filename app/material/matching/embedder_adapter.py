from __future__ import annotations

import logging

from app.material.logging_utils import log_json, preview_texts, summarize_vectors
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class EmbedderAdapter:
    """Adapt EmbeddingService to TextEmbedder protocol."""

    def __init__(self, embedding_service: EmbeddingService):
        self._embedding_service = embedding_service

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            raise ValueError("texts must not be empty")

        logger.info(
            "Embedding start text_count=%s previews=%s",
            len(texts),
            preview_texts(texts),
        )
        payload = [{"type": "text", "text": text or " "} for text in texts]
        log_json(logger, logging.INFO, "Embedding batch request", {"input": payload})
        vectors = self._embedding_service.embed(input_items=payload)
        log_json(logger, logging.INFO, "Embedding batch response", summarize_vectors(vectors))

        if len(vectors) == len(texts):
            logger.info("Embedding finished mode=batch vector_count=%s", len(vectors))
            return vectors

        logger.info(
            "Embedding batch count mismatch expected=%s actual=%s, fallback to sequential",
            len(texts),
            len(vectors),
        )
        vectors = self._embed_texts_sequentially(texts)
        logger.info("Embedding finished mode=sequential vector_count=%s", len(vectors))
        return vectors

    def _embed_texts_sequentially(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for index, text in enumerate(texts):
            item_payload = [{"type": "text", "text": text or " "}]
            log_json(
                logger,
                logging.INFO,
                f"Embedding sequential request index={index}",
                {"input": item_payload},
            )
            item_vectors = self._embedding_service.embed(input_items=item_payload)
            log_json(
                logger,
                logging.INFO,
                f"Embedding sequential response index={index}",
                summarize_vectors(item_vectors),
            )
            if len(item_vectors) != 1:
                raise ValueError(
                    f"expected 1 embedding for single text, got {len(item_vectors)}"
                )
            vectors.append(item_vectors[0])
        return vectors
