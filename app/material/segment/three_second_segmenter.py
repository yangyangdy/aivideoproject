from __future__ import annotations

import logging

from app.material.config import MaterialSettings
from app.material.domain.models import SegmentDraft, WordToken
from app.material.logging_utils import log_json, truncate_text
from app.material.segment.fixed_window import build_windows, words_to_text
from app.material.segment.semantic_borrow import apply_semantic_borrow

logger = logging.getLogger(__name__)


class ThreeSecondSegmenter:
    def __init__(self, settings: MaterialSettings):
        self.settings = settings

    def segment(self, words: list[WordToken], duration_ms: int) -> list[SegmentDraft]:
        window_ms = self.settings.segment_duration_ms
        windows = build_windows(words, duration_ms, window_ms)
        raw_texts = [words_to_text(window.words) for window in windows]

        # 语义借词只影响检索文本，不改变逐词硬切得到的 raw_text。
        apply_semantic_borrow(windows, self.settings)

        drafts: list[SegmentDraft] = []
        step_sec = window_ms // 1000
        segment_snapshots: list[dict[str, str | int]] = []
        for window in windows:
            borrowed_text = words_to_text(window.words)
            start_sec = window.index * step_sec
            end_sec = start_sec + step_sec
            drafts.append(
                SegmentDraft(
                    index=window.index,
                    start_sec=start_sec,
                    end_sec=end_sec,
                    raw_text=raw_texts[window.index],
                    text=borrowed_text,
                    query_text=borrowed_text,
                )
            )
            segment_snapshots.append(
                {
                    "index": window.index,
                    "start_sec": start_sec,
                    "end_sec": end_sec,
                    "raw_text": truncate_text(raw_texts[window.index], 120),
                    "borrowed_text": truncate_text(borrowed_text, 120),
                    "query_text": truncate_text(borrowed_text, 120),
                }
            )

        self._fill_query_texts(drafts)

        for draft in drafts:
            if draft.query_text != draft.text:
                segment_snapshots[draft.index]["query_text"] = truncate_text(draft.query_text, 120)

        log_json(logger, logging.INFO, "segment windows raw vs borrowed", segment_snapshots)

        return drafts

    def _fill_query_texts(self, drafts: list[SegmentDraft]) -> None:
        """静音空窗没有语义补全文本时，检索沿用邻段的补全文本。"""
        for index, draft in enumerate(drafts):
            if draft.query_text:
                continue
            draft.query_text = _nearest_non_empty_borrowed_text(drafts, index)


def _nearest_non_empty_borrowed_text(drafts: list[SegmentDraft], index: int) -> str:
    for offset in range(1, len(drafts)):
        prev_index = index - offset
        if prev_index >= 0 and drafts[prev_index].text:
            return drafts[prev_index].text
        next_index = index + offset
        if next_index < len(drafts) and drafts[next_index].text:
            return drafts[next_index].text
    return ""
