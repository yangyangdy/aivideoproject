from __future__ import annotations

import json
import logging
from typing import Any

SENSITIVE_HEADER_KEYS = frozenset(
    {"authorization", "x-api-key", "x-api-app-key", "x-api-access-key"}
)


def mask_secret(value: str, visible: int = 4) -> str:
    text = value or ""
    if len(text) <= visible * 2:
        return "***"
    return f"{text[:visible]}***{text[-visible:]}"


def mask_headers(headers: dict[str, str] | None) -> dict[str, str]:
    if not headers:
        return {}
    masked: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in SENSITIVE_HEADER_KEYS:
            masked[key] = mask_secret(value)
        else:
            masked[key] = value
    return masked


def summarize_vectors(vectors: list[list[float]]) -> dict[str, Any]:
    if not vectors:
        return {"count": 0}
    return {
        "count": len(vectors),
        "dimension": len(vectors[0]),
    }


def truncate_text(text: str, max_len: int = 500) -> str:
    if len(text) <= max_len:
        return text
    return f"{text[:max_len]}...({len(text)} chars)"


def log_json(logger: logging.Logger, level: int, message: str, payload: Any, max_len: int = 3000) -> None:
    try:
        text = json.dumps(payload, ensure_ascii=False, default=str)
    except TypeError:
        text = str(payload)
    if len(text) > max_len:
        text = f"{text[:max_len]}...({len(text)} chars)"
    logger.log(level, "%s %s", message, text)


def preview_texts(texts: list[str], limit: int = 5, max_len: int = 80) -> list[str]:
    previews = [truncate_text(text, max_len) for text in texts[:limit]]
    if len(texts) > limit:
        previews.append(f"... and {len(texts) - limit} more")
    return previews


def summarize_words_from_result(utterances: list[Any]) -> list[dict[str, Any]]:
    words: list[dict[str, Any]] = []
    for utterance_index, utterance in enumerate(utterances):
        if not isinstance(utterance, dict):
            continue
        for word in utterance.get("words") or []:
            if not isinstance(word, dict):
                continue
            text = str(word.get("text") or "").strip()
            if not text:
                continue
            item: dict[str, Any] = {
                "utterance_index": utterance_index,
                "start_time": word.get("start_time"),
                "end_time": word.get("end_time"),
                "text": text,
            }
            if word.get("confidence") is not None:
                item["confidence"] = word.get("confidence")
            words.append(item)
    return words


def summarize_word_tokens(words: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "utterance_index": word.utterance_index,
            "start_time": word.start_ms,
            "end_time": word.end_ms,
            "text": word.text,
        }
        for word in words
    ]


def summarize_utterances(utterances: list[Any]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for utterance in utterances:
        if not isinstance(utterance, dict):
            continue
        summary.append(
            {
                "start_time": utterance.get("start_time"),
                "end_time": utterance.get("end_time"),
                "text": utterance.get("text") or "",
            }
        )
    return summary


def log_asr_transcript(
    logger: logging.Logger,
    *,
    audio_url: str,
    result: dict[str, Any],
    source: str,
) -> None:
    full_text = str(result.get("text") or "")
    utterances = result.get("utterances") or []
    additions = result.get("additions") or {}

    raw_words = summarize_words_from_result(utterances)
    log_json(
        logger,
        logging.INFO,
        "match_segments asr transcript meta",
        {
            "source": source,
            "audio_url": audio_url or None,
            "duration_ms": additions.get("duration"),
            "utterance_count": len(utterances),
            "word_count": len(raw_words),
            "word_level": bool(raw_words),
            "full_text_chars": len(full_text),
        },
    )
    logger.info(
        "match_segments asr full_text source=%s audio_url=%s chars=%s\n%s",
        source,
        audio_url or "(none)",
        len(full_text),
        full_text,
    )
    subtitles = result.get("subtitles") or []
    if subtitles:
        log_json(
            logger,
            logging.INFO,
            "match_segments asr subtitles",
            subtitles,
            max_len=500_000,
        )
    if raw_words:
        log_json(
            logger,
            logging.INFO,
            "match_segments asr words",
            raw_words,
            max_len=500_000,
        )
    elif utterances:
        logger.warning(
            "match_segments asr words missing, only utterance-level timestamps available utterance_count=%s",
            len(utterances),
        )
        log_json(
            logger,
            logging.INFO,
            "match_segments asr utterances",
            summarize_utterances(utterances),
            max_len=100_000,
        )
