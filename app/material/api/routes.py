from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.material.api.version import MATCH_API_VERSION, MATCH_SEGMENT_FIELDS
from app.material.dependencies import get_match_orchestrator
from app.material.matching.orchestrator import MatchOrchestrator
from app.material.schemas.match import MatchSegmentsRequest, MatchSegmentsResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/material", tags=["material"])


@router.get("/info")
def material_info() -> dict[str, object]:
    return {
        "api_version": MATCH_API_VERSION,
        "segment_fields": list(MATCH_SEGMENT_FIELDS),
        "match_endpoint": "POST /material/match-segments",
    }


@router.post("/match-segments", response_model=MatchSegmentsResponse)
def match_segments(
    request: MatchSegmentsRequest,
    orchestrator: MatchOrchestrator = Depends(get_match_orchestrator),
) -> MatchSegmentsResponse:
    payload = request.to_payload()
    result = payload.get("result") or {}
    logger.info(
        "match_segments route api_version=%s uid=%s audio_url=%s utterance_count=%s candidate_count=%s",
        MATCH_API_VERSION,
        payload.get("uid"),
        payload.get("audio_url") or "-",
        len(result.get("utterances") or []),
        len(payload.get("candidate_material_ids") or []),
    )

    raw_result = orchestrator.match_segments(payload)
    _validate_segment_payload(raw_result.get("segments") or [])

    response = MatchSegmentsResponse.model_validate(raw_result)
    if response.segments:
        first = response.segments[0]
        logger.info(
            "match_segments route response verified api_version=%s segment0 raw_text_len=%s query_text_len=%s text_eq_raw=%s",
            MATCH_API_VERSION,
            len(first.raw_text),
            len(first.query_text),
            first.text == first.raw_text,
        )
    return response


def _validate_segment_payload(segments: list[object]) -> None:
    required = set(MATCH_SEGMENT_FIELDS)
    for index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            raise HTTPException(status_code=500, detail=f"segment {index} is not a dict")
        missing = required - set(segment.keys())
        if missing:
            logger.error(
                "match_segments invalid segment payload index=%s missing=%s keys=%s",
                index,
                sorted(missing),
                sorted(segment.keys()),
            )
            raise HTTPException(
                status_code=500,
                detail=f"segment {index} missing fields: {', '.join(sorted(missing))}",
            )
