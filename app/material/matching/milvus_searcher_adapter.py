from __future__ import annotations

import logging
from typing import Any

from app.material.config import MaterialSettings
from app.material.domain.models import SearchHit
from app.material.logging_utils import log_json
from app.services.milvus_service import MilvusService

logger = logging.getLogger(__name__)


class MilvusSearcherAdapter:
    """Adapt MilvusService to VectorSearcher protocol."""

    def __init__(self, milvus_service: MilvusService, settings: MaterialSettings):
        self._milvus_service = milvus_service
        self._settings = settings

    def search_top1(
        self,
        vectors: list[list[float]],
        filter_expr: str,
        *,
        strict_filter: bool = False,
    ) -> list[SearchHit | None]:
        if not vectors:
            return []

        logger.info(
            "Milvus search_top1 start vector_count=%s filter=%s strict_filter=%s batch_size=%s",
            len(vectors),
            filter_expr,
            strict_filter,
            self._settings.milvus_search_batch_size,
        )
        hits = self._search_batched(vectors, filter_expr)
        if self._all_segments_matched(hits):
            logger.info("Milvus search_top1 matched with filter=%s", filter_expr)
            return hits

        if filter_expr and not strict_filter:
            logger.info("Milvus search_top1 retry without filter")
            hits = self._search_batched(vectors, "")
            if self._all_segments_matched(hits):
                logger.info("Milvus search_top1 matched without filter")
                return hits

        hits = self._apply_fallback(hits, strict_filter=strict_filter)
        matched = sum(1 for hit in hits if hit is not None)
        logger.info("Milvus search_top1 finished matched=%s total=%s", matched, len(hits))
        return hits

    def _search_batched(self, vectors: list[list[float]], filter_expr: str) -> list[SearchHit | None]:
        batch_size = max(1, self._settings.milvus_search_batch_size)
        parsed: list[SearchHit | None] = []
        for offset in range(0, len(vectors), batch_size):
            chunk = vectors[offset : offset + batch_size]
            parsed.extend(self._search_once(chunk, filter_expr, offset=offset))
        return parsed

    def _search_once(
        self,
        vectors: list[list[float]],
        filter_expr: str,
        *,
        offset: int = 0,
    ) -> list[SearchHit | None]:
        request_meta = {
            "offset": offset,
            "vector_count": len(vectors),
            "limit": 1,
            "filter": filter_expr,
            "output_fields": ["material_id", "uid", "tag"],
        }
        log_json(logger, logging.INFO, "Milvus search request", request_meta)

        raw = self._milvus_service.search(
            data=vectors,
            limit=1,
            filter=filter_expr,
            output_fields=["material_id", "uid", "tag"],
        )

        response_summary = []
        chunk_hits: list[SearchHit | None] = []
        for index, row in enumerate(raw):
            hit = self._parse_top_hit(row)
            chunk_hits.append(hit)
            response_summary.append(
                {
                    "index": offset + index,
                    "material_id": hit.material_id if hit else None,
                    "score": hit.score if hit else None,
                }
            )
        while len(chunk_hits) < len(vectors):
            chunk_hits.append(None)
            response_summary.append({"index": offset + len(chunk_hits) - 1, "material_id": None, "score": None})

        log_json(logger, logging.INFO, "Milvus search response", response_summary[: len(vectors)])
        return chunk_hits[: len(vectors)]

    @staticmethod
    def _parse_top_hit(row: Any) -> SearchHit | None:
        if not row:
            return None
        top = row[0] if isinstance(row, list) else row
        if not isinstance(top, dict):
            return None
        entity = top.get("entity") or {}
        material_id = entity.get("material_id", top.get("material_id"))
        if material_id is None:
            return None
        score = float(top.get("distance", 0.0))
        return SearchHit(material_id=int(material_id), score=score)

    @staticmethod
    def _all_segments_matched(hits: list[SearchHit | None]) -> bool:
        return bool(hits) and all(hit is not None for hit in hits)

    def _apply_fallback(
        self,
        hits: list[SearchHit | None],
        *,
        strict_filter: bool = False,
    ) -> list[SearchHit | None]:
        if strict_filter:
            return hits
        fallback_id = self._settings.match_fallback_material_id
        if fallback_id <= 0:
            return hits
        result: list[SearchHit | None] = []
        for hit in hits:
            if hit is None:
                result.append(SearchHit(material_id=fallback_id, score=0.0))
            else:
                result.append(hit)
        return result
