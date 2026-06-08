from __future__ import annotations

from typing import Any


def normalize_word(word: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(word, dict):
        return None
    text = str(word.get("text") or "").strip()
    if not text:
        return None
    return {
        "text": text,
        "start_time": int(word.get("start_time") or word.get("start") or 0),
        "end_time": int(word.get("end_time") or word.get("end") or 0),
    }


def normalize_utterance(utterance: dict[str, Any]) -> dict[str, Any]:
    words: list[dict[str, Any]] = []
    for word in utterance.get("words") or []:
        if not isinstance(word, dict):
            continue
        normalized = normalize_word(word)
        if normalized:
            words.append(normalized)

    return {
        "start_time": int(utterance.get("start_time") or utterance.get("start") or 0),
        "end_time": int(utterance.get("end_time") or utterance.get("end") or 0),
        "text": str(utterance.get("text") or ""),
        "words": words,
    }


def build_subtitles(utterances: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build document-style subtitles with per-word timestamps."""
    subtitles: list[dict[str, Any]] = []
    for utterance in utterances:
        subtitles.append(
            {
                "start": utterance["start_time"],
                "end": utterance["end_time"],
                "text": utterance["text"],
                "words": [
                    {
                        "text": word["text"],
                        "start": word["start_time"],
                        "end": word["end_time"],
                    }
                    for word in utterance.get("words") or []
                ],
            }
        )
    return subtitles


def normalize_asr_result(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize Volcano ASR API response into match-segments result shape."""
    if "result" in data and isinstance(data["result"], dict):
        source = data["result"]
    else:
        source = data

    additions = source.get("additions") or {}
    if not additions and source.get("duration") is not None:
        additions = {"duration": source.get("duration")}

    utterances = [
        normalize_utterance(item)
        for item in (source.get("utterances") or [])
        if isinstance(item, dict)
    ]

    return {
        "text": source.get("text") or "",
        "utterances": utterances,
        "subtitles": build_subtitles(utterances),
        "additions": additions,
    }


def extract_duration_ms(data: dict[str, Any], result: dict[str, Any]) -> int:
    audio_info = data.get("audio_info") or {}
    additions = result.get("additions") or {}
    for value in (
        audio_info.get("duration"),
        additions.get("duration"),
        data.get("duration"),
        result.get("duration"),
    ):
        if value is None or value == "":
            continue
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            return parsed
    return 0


def merge_asr_into_payload(payload: dict[str, Any], asr_data: dict[str, Any]) -> dict[str, Any]:
    merged = dict(payload)
    result = normalize_asr_result(asr_data)
    merged["result"] = result

    audio_info = dict(merged.get("audio_info") or {})
    duration_ms = extract_duration_ms(asr_data, result)
    if duration_ms > 0 and not audio_info.get("duration"):
        audio_info["duration"] = duration_ms
    if audio_info:
        merged["audio_info"] = audio_info
    return merged
