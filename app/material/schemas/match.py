from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class AsrWord(BaseModel):
    start_time: int
    end_time: int
    text: str
    confidence: float | None = None


class AsrUtterance(BaseModel):
    start_time: int
    end_time: int
    text: str = ""
    words: list[AsrWord] = Field(default_factory=list)


class AsrAdditions(BaseModel):
    duration: str | int | None = None


class AsrResult(BaseModel):
    additions: AsrAdditions | None = None
    text: str = ""
    utterances: list[AsrUtterance] = Field(default_factory=list)


class AudioInfo(BaseModel):
    duration: int | None = None


class MatchSegmentsRequest(BaseModel):
    uid: int
    filter: str | None = None
    candidate_material_ids: list[int] = Field(default_factory=list)
    audio_url: str | None = None
    audio_info: AudioInfo | None = None
    result: AsrResult | None = None

    @model_validator(mode="after")
    def validate_input(self) -> MatchSegmentsRequest:
        audio_url = (self.audio_url or "").strip()
        utterances = self.result.utterances if self.result else []

        if not audio_url and not utterances:
            raise ValueError("audio_url or result.utterances is required")

        if utterances:
            duration = None
            if self.audio_info and self.audio_info.duration:
                duration = int(self.audio_info.duration)
            elif self.result and self.result.additions and self.result.additions.duration not in (None, ""):
                duration = int(self.result.additions.duration)
            if not duration or duration <= 0:
                raise ValueError("audio_info.duration or result.additions.duration is required when result.utterances is provided")
        return self

    def to_payload(self) -> dict[str, Any]:
        data = self.model_dump(mode="json", exclude_none=True)
        if "result" not in data:
            data["result"] = {"utterances": [], "text": ""}
        return data


class MatchedSegment(BaseModel):
    index: int
    start_sec: int
    end_sec: int
    raw_text: str
    query_text: str
    text: str
    material_id: int
    similarity_score: float


class MatchSegmentsResponse(BaseModel):
    api_version: str = "v2-dual-text"
    audio_duration_ms: int
    segment_duration_sec: int
    total_segments: int
    segments: list[MatchedSegment]
