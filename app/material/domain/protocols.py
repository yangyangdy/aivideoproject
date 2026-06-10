from __future__ import annotations

from typing import Any, Protocol

from app.material.domain.asr_models import AsrQueryResult, AsrRecognizeResult, AsrSubmitResult
from app.material.domain.models import ParsedAsr, SearchHit, SegmentDraft, WordToken


class AsrClient(Protocol):
    """Abstraction for speech-to-text providers."""

    def submit_task(self, audio_url: str, *, uid: int = 0, **kwargs: Any) -> AsrSubmitResult: ...

    def query_task(self, task_id: str, *, x_tt_logid: str = "", **kwargs: Any) -> AsrQueryResult: ...

    def recognize(self, audio_url: str, *, uid: int = 0, **kwargs: Any) -> AsrRecognizeResult: ...


class AsrParser(Protocol):
    def parse(self, payload: dict[str, Any]) -> ParsedAsr: ...


class Segmenter(Protocol):
    def segment(
        self,
        words: list[WordToken],
        duration_ms: int,
        *,
        segment_count: int | None = None,
    ) -> list[SegmentDraft]: ...


class TextEmbedder(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


class VectorSearcher(Protocol):
    def search_top1(
        self,
        vectors: list[list[float]],
        filter_expr: str,
        *,
        strict_filter: bool = False,
    ) -> list[SearchHit | None]: ...
