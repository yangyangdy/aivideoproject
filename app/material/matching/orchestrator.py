from __future__ import annotations

import logging
from typing import Any

from app.material.config import MaterialSettings
from app.material.domain.models import SearchHit
from app.material.domain.protocols import AsrClient, AsrParser, Segmenter, TextEmbedder, VectorSearcher
from app.material.asr.payload_builder import merge_asr_into_payload
from app.material.logging_utils import log_asr_transcript, log_json, summarize_word_tokens, truncate_text
from app.material.parsers.volcano_asr_parser import VolcanoAsrParser
from app.material.api.version import MATCH_API_VERSION
from app.material.segment.three_second_segmenter import ThreeSecondSegmenter

logger = logging.getLogger(__name__)

class MatchOrchestrator:
    def __init__(
        self,
        *,
        settings: MaterialSettings,
        parser: AsrParser | None = None,
        segmenter: Segmenter | None = None,
        embedder: TextEmbedder,
        searcher: VectorSearcher,
        asr_client: AsrClient | None = None,
    ):
        self._settings = settings
        self._parser = parser or VolcanoAsrParser()
        self._segmenter = segmenter or ThreeSecondSegmenter(settings)
        self._embedder = embedder
        self._searcher = searcher
        self._asr_client = asr_client

    def match_segments(self, payload: dict[str, Any]) -> dict[str, Any]:
        logger.info(
            "match_segments start uid=%s has_audio_url=%s has_result=%s",
            payload.get("uid"),
            bool(payload.get("audio_url")),
            bool((payload.get("result") or {}).get("utterances")),
        )
        payload, asr_source = self._resolve_asr_payload(payload)
        self._log_asr_transcript(payload, source=asr_source)
        uid = int(payload.get("uid") or 0)
        filter_expr, strict_filter = _build_search_filter(
            uid=uid,
            filter_override=payload.get("filter"),
            candidate_material_ids=payload.get("candidate_material_ids") or [],
        )
        if strict_filter:
            logger.info(
                "match_segments candidate_material_ids count=%s filter=%s",
                len(payload.get("candidate_material_ids") or []),
                filter_expr,
            )

        parsed = self._parser.parse(payload)
        logger.info(
            "match_segments parsed duration_ms=%s word_count=%s text_preview=%s",
            parsed.duration_ms,
            len(parsed.words),
            truncate_text(parsed.full_text, 120),
        )
        log_json(
            logger,
            logging.INFO,
            "match_segments asr words parsed",
            summarize_word_tokens(parsed.words),
            max_len=500_000,
        )

        segments = self._segmenter.segment(parsed.words, parsed.duration_ms)
        if not segments:
            raise ValueError("no segments generated from ASR payload")

        _validate_candidate_pool_size(
            payload.get("candidate_material_ids") or [],
            segment_count=len(segments),
        )

        # 接口 text=逐词硬切；向量检索=语义补全后的 query_text。
        query_texts = [segment.query_text or segment.text or " " for segment in segments]
        log_json(
            logger,
            logging.INFO,
            "match_segments segment texts for retrieval",
            [
                {
                    "index": segment.index,
                    "start_sec": segment.start_sec,
                    "end_sec": segment.end_sec,
                    "text": truncate_text(segment.raw_text, 120),
                    "raw_text": truncate_text(segment.raw_text, 120),
                    "borrowed_text": truncate_text(segment.text, 120),
                    "query_text": truncate_text(query_text, 120),
                }
                for segment, query_text in zip(segments, query_texts)
            ],
        )
        vectors = self._embedder.embed_texts(query_texts)
        if len(vectors) != len(segments):
            raise ValueError(
                f"embedding count mismatch: segments={len(segments)}, vectors={len(vectors)}"
            )

        hits = self._search_unique_hits(vectors, filter_expr, strict_filter=strict_filter)

        if any(hit is None for hit in hits):
            unmatched = sum(1 for hit in hits if hit is None)
            used_count = len({hit.material_id for hit in hits if hit is not None})
            raise ValueError(
                "向量库无可用素材: "
                f"filter={filter_expr}, unmatched_segments={unmatched}/{len(hits)}, "
                f"unique_material_ids={used_count}"
            )

        segment_duration_sec = self._settings.segment_duration_ms // 1000
        matched_segments = []
        for segment, hit in zip(segments, hits):
            assert hit is not None
            raw_text = segment.raw_text
            query_text = segment.query_text or segment.text or ""
            matched_segments.append(
                {
                    "index": segment.index,
                    "start_sec": segment.start_sec,
                    "end_sec": segment.end_sec,
                    "raw_text": raw_text,
                    "query_text": query_text,
                    "text": raw_text,
                    "material_id": hit.material_id,
                    "similarity_score": round(hit.score, 4),
                }
            )

        logger.info(
            "match_segments finished total=%s first_material_id=%s first_score=%s",
            len(matched_segments),
            matched_segments[0]["material_id"] if matched_segments else None,
            matched_segments[0]["similarity_score"] if matched_segments else None,
        )
        log_json(logger, logging.INFO, "match_segments response preview", matched_segments[:3])
        if matched_segments:
            first = matched_segments[0]
            logger.info(
                "match_segments response built api_version=%s keys=%s raw_text_len=%s query_text_len=%s",
                MATCH_API_VERSION,
                sorted(first.keys()),
                len(first.get("raw_text") or ""),
                len(first.get("query_text") or ""),
            )

        return {
            "api_version": MATCH_API_VERSION,
            "audio_duration_ms": parsed.duration_ms,
            "segment_duration_sec": segment_duration_sec,
            "total_segments": len(matched_segments),
            "segments": matched_segments,
        }

    def _log_asr_transcript(self, payload: dict[str, Any], *, source: str) -> None:
        result = payload.get("result") or {}
        audio_url = str(payload.get("audio_url") or "").strip()
        log_asr_transcript(
            logger,
            audio_url=audio_url,
            result=result,
            source=source,
        )

    def _resolve_asr_payload(self, payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
        result = payload.get("result") or {}
        utterances = result.get("utterances") or []
        if utterances:
            logger.info("match_segments using provided ASR result utterance_count=%s", len(utterances))
            return payload, "provided_result"

        audio_url = str(payload.get("audio_url") or "").strip()
        if not audio_url:
            raise ValueError("audio_url or result.utterances is required")

        if self._asr_client is None:
            raise ValueError("ASR client is not configured")

        uid = int(payload.get("uid") or 0)
        logger.info("match_segments calling ASR recognize audio_url=%s uid=%s", audio_url, uid)
        recognize = self._asr_client.recognize(audio_url, uid=uid)
        if not recognize.success:
            raise ValueError(recognize.error or "ASR recognition failed")

        merged = merge_asr_into_payload(payload, recognize.data)
        logger.info(
            "match_segments ASR completed task_id=%s utterance_count=%s",
            recognize.task_id,
            len((merged.get("result") or {}).get("utterances") or []),
        )
        return merged, "asr_recognize"

    def _search_unique_hits(
        self,
        vectors: list[list[float]],
        filter_expr: str,
        *,
        strict_filter: bool,
    ) -> list[SearchHit | None]:
        used_material_ids: list[int] = []
        hits: list[SearchHit | None] = []
        for index, vector in enumerate(vectors):
            segment_filter = _append_excluded_material_ids(filter_expr, used_material_ids)
            segment_strict = strict_filter or bool(used_material_ids)
            segment_hits = self._searcher.search_top1(
                [vector],
                segment_filter,
                strict_filter=segment_strict,
            )
            if len(segment_hits) != 1:
                raise ValueError(
                    f"vector search result count mismatch: segment={index}, hits={len(segment_hits)}"
                )
            hit = segment_hits[0]
            if hit is not None:
                if hit.material_id in used_material_ids:
                    logger.warning(
                        "match_segments duplicate material_id returned segment=%s material_id=%s filter=%s",
                        index,
                        hit.material_id,
                        segment_filter,
                    )
                    hit = None
                else:
                    used_material_ids.append(hit.material_id)
            hits.append(hit)
            logger.info(
                "match_segments segment search index=%s material_id=%s score=%s used_count=%s",
                index,
                hit.material_id if hit else None,
                round(hit.score, 4) if hit else None,
                len(used_material_ids),
            )
        return hits


def _validate_candidate_pool_size(
    candidate_material_ids: list[int] | list[object],
    *,
    segment_count: int,
) -> None:
    unique_count = len({int(material_id) for material_id in candidate_material_ids})
    if unique_count == 0:
        return
    if unique_count < segment_count:
        raise ValueError(
            "候选素材池过小: "
            f"candidate_count={unique_count}, segment_count={segment_count}, "
            "候选素材数量需不少于片段数"
        )


def _append_excluded_material_ids(filter_expr: str, excluded_material_ids: list[int]) -> str:
    if not excluded_material_ids:
        return filter_expr
    exclude_expr = (
        f"material_id not in [{', '.join(str(material_id) for material_id in excluded_material_ids)}]"
    )
    if filter_expr:
        return f"({filter_expr}) and ({exclude_expr})"
    return exclude_expr


def _build_search_filter(
    *,
    uid: int,
    filter_override: object,
    candidate_material_ids: list[int] | list[object],
) -> tuple[str, bool]:
    custom = str(filter_override or "").strip()
    ids = sorted({int(material_id) for material_id in candidate_material_ids})
    if not ids:
        return custom or f"uid == {uid}", False

    ids_expr = f"material_id in [{', '.join(str(material_id) for material_id in ids)}]"
    if custom:
        return f"({custom}) and ({ids_expr})", True
    # 候选列表已是检索范围，不再叠加 uid 过滤，避免候选素材 uid 与请求 uid 不一致时被误筛空。
    return ids_expr, True