from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.material.domain.models import WordToken


@dataclass
class WindowWords:
    index: int
    start_ms: int
    end_ms: int
    words: list[WordToken] = field(default_factory=list)


def build_windows(words: list[WordToken], duration_ms: int, window_ms: int) -> list[WindowWords]:
    if window_ms <= 0:
        raise ValueError("window_ms must be positive")
    segment_count = max(1, math.ceil(duration_ms / window_ms))
    windows = [
        WindowWords(
            index=index,
            start_ms=index * window_ms,
            end_ms=(index + 1) * window_ms,
            words=[],
        )
        for index in range(segment_count)
    ]
    for word in words:
        window_index = _window_index_for_word(word, window_ms, segment_count)
        windows[window_index].words.append(word)
    for window in windows:
        window.words.sort(key=lambda item: (item.start_ms, item.end_ms))
    return windows


def _overlap_ms(word_start: int, word_end: int, window_start: int, window_end: int) -> int:
    overlap_start = max(word_start, window_start)
    overlap_end = min(word_end, window_end)
    return max(0, overlap_end - overlap_start)


def _window_index_for_word(word: WordToken, window_ms: int, segment_count: int) -> int:
    """按词级 start/end 与 3 秒窗的重叠时长聚合，重叠相同则归入更早的时间窗。"""
    best_index = 0
    best_overlap = -1
    for index in range(segment_count):
        window_start = index * window_ms
        window_end = window_start + window_ms
        overlap = _overlap_ms(word.start_ms, word.end_ms, window_start, window_end)
        if overlap > best_overlap:
            best_overlap = overlap
            best_index = index
    if best_overlap <= 0:
        return min(max(word.start_ms, 0) // window_ms, segment_count - 1)
    return best_index


def words_to_text(words: list[WordToken]) -> str:
    return "".join(word.text for word in words)
