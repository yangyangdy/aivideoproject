from __future__ import annotations

import logging

from app.material.config import MaterialSettings
from app.material.domain.models import SegmentDraft, WordToken
from app.material.logging_utils import log_json, truncate_text
from app.material.segment.fixed_window import build_windows, words_to_text
from app.material.segment.semantic_borrow import build_query_text

logger = logging.getLogger(__name__)


class ThreeSecondSegmenter:
    def __init__(self, settings: MaterialSettings):
        self.settings = settings

    def segment(
        self,
        words: list[WordToken],
        duration_ms: int,
        *,
        segment_count: int | None = None,
    ) -> list[SegmentDraft]:
        if segment_count is not None:
            windows = build_windows(words, duration_ms, segment_count=segment_count)
        else:
            window_ms = self.settings.segment_duration_ms
            windows = build_windows(words, duration_ms, window_ms=window_ms)

        raw_word_lists = [list(window.words) for window in windows]
        raw_texts = [words_to_text(words) for words in raw_word_lists]

        drafts: list[SegmentDraft] = []
        segment_snapshots: list[dict[str, str | int]] = []
        for window in windows:
            raw_text = raw_texts[window.index]
            query_text = build_query_text(window.index, raw_word_lists, self.settings)
            start_sec = window.start_ms // 1000
            end_sec = window.end_ms // 1000
            drafts.append(
                SegmentDraft(
                    index=window.index,
                    start_sec=start_sec,
                    end_sec=end_sec,
                    raw_text=raw_text,
                    text=raw_text,
                    query_text=query_text,
                )
            )
            segment_snapshots.append(
                {
                    "index": window.index,
                    "start_sec": start_sec,
                    "end_sec": end_sec,
                    "raw_text": truncate_text(raw_text, 120),
                    "borrowed_text": truncate_text(query_text, 120),
                    "query_text": truncate_text(query_text, 120),
                }
            )

        self._fill_query_texts(drafts)

        log_json(logger, logging.INFO, "segment windows raw vs borrowed", segment_snapshots)

        return drafts

    def _fill_query_texts(self, drafts: list[SegmentDraft]) -> None:
        """静音空窗没有口播词时，检索沿用邻段 query_text。"""
        for index, draft in enumerate(drafts):
            if draft.query_text:
                continue
            draft.query_text = _nearest_non_empty_query_text(drafts, index)


def _nearest_non_empty_query_text(drafts: list[SegmentDraft], index: int) -> str:
    for offset in range(1, len(drafts)):
        prev_index = index - offset
        if prev_index >= 0 and drafts[prev_index].query_text:
            return drafts[prev_index].query_text
        next_index = index + offset
        if next_index < len(drafts) and drafts[next_index].query_text:
            return drafts[next_index].query_text
    return ""
