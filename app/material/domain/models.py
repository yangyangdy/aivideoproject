from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class WordToken:
    start_ms: int
    end_ms: int
    text: str
    utterance_index: int = 0


@dataclass
class SegmentDraft:
    index: int
    start_sec: int
    end_sec: int
    raw_text: str = ""
    text: str = ""
    query_text: str = ""


@dataclass(frozen=True)
class SearchHit:
    material_id: int
    score: float


@dataclass(frozen=True)
class ParsedAsr:
    duration_ms: int
    words: list[WordToken] = field(default_factory=list)
    full_text: str = ""
