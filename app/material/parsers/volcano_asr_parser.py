from __future__ import annotations

from typing import Any

from app.material.domain.models import ParsedAsr, WordToken


class VolcanoAsrParser:
    """Parse Volcano/PHP ASR JSON payload into domain models."""

    def parse(self, payload: dict[str, Any]) -> ParsedAsr:
        audio_info = payload.get("audio_info") or {}
        result = payload.get("result") or {}
        additions = result.get("additions") or {}

        duration_ms = _coerce_duration_ms(
            audio_info.get("duration"),
            additions.get("duration"),
        )
        if duration_ms <= 0:
            raise ValueError("audio duration is required (audio_info.duration or result.additions.duration)")

        words: list[WordToken] = []
        utterances = result.get("utterances") or []
        for utterance_index, utterance in enumerate(utterances):
            if not isinstance(utterance, dict):
                continue
            for word in utterance.get("words") or []:
                if not isinstance(word, dict):
                    continue
                text = str(word.get("text") or "").strip()
                if not text:
                    continue
                words.append(
                    WordToken(
                        start_ms=int(word.get("start_time") or 0),
                        end_ms=int(word.get("end_time") or 0),
                        text=text,
                        utterance_index=utterance_index,
                    )
                )

        words.sort(key=lambda item: (item.start_ms, item.end_ms))

        if not words:
            words = _fallback_utterance_words(utterances)

        full_text = str(result.get("text") or "").strip()
        return ParsedAsr(duration_ms=duration_ms, words=words, full_text=full_text)


def _coerce_duration_ms(*values: Any) -> int:
    for value in values:
        if value is None or value == "":
            continue
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            return parsed
    return 0


def _fallback_utterance_words(utterances: list[Any]) -> list[WordToken]:
    """When word-level timestamps are missing, assign whole utterances by time overlap later."""
    words: list[WordToken] = []
    for utterance_index, utterance in enumerate(utterances):
        if not isinstance(utterance, dict):
            continue
        text = str(utterance.get("text") or "").strip()
        if not text:
            continue
        words.append(
            WordToken(
                start_ms=int(utterance.get("start_time") or 0),
                end_ms=int(utterance.get("end_time") or 0),
                text=text,
                utterance_index=utterance_index,
            )
        )
    words.sort(key=lambda item: (item.start_ms, item.end_ms))
    return words
