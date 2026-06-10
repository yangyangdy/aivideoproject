from __future__ import annotations

from app.material.config import MaterialSettings
from app.material.domain.models import WordToken
from app.material.segment.fixed_window import WindowWords, words_to_text


def apply_semantic_borrow(windows: list[WindowWords], settings: MaterialSettings) -> None:
    if not windows:
        return

    endings = settings.segment_sentence_endings
    max_borrow = settings.segment_max_borrow_words
    min_chars = settings.segment_min_chars
    max_chars = settings.segment_max_chars

    # 仅从左到右尾借 + 向前补短，避免头借把上一段刚借来的词又拉回下一段。
    _pass_tail_borrow(windows, endings, max_borrow, max_chars)
    _pass_fill_short(windows, endings, max_borrow, min_chars, max_chars)


def build_query_text(
    index: int,
    window_words: list[list[WordToken]],
    settings: MaterialSettings,
) -> str:
    """Extend raw window words for retrieval without mutating neighbor allocations."""
    endings = settings.segment_sentence_endings
    max_borrow = settings.segment_max_borrow_words
    min_chars = settings.segment_min_chars
    max_chars = settings.segment_max_chars

    core = list(window_words[index])
    if not core:
        return ""

    query_words = _extend_query_head(
        core,
        window_words[index - 1] if index > 0 else [],
        max_borrow,
        endings,
        max_chars,
    )
    query_words = _extend_query_tail(
        query_words,
        window_words[index + 1] if index + 1 < len(window_words) else [],
        max_borrow,
        endings,
        max_chars,
    )

    text = words_to_text(query_words)
    if text and len(text) < min_chars and index + 1 < len(window_words):
        query_words = _extend_query_tail(
            query_words,
            window_words[index + 1],
            max_borrow,
            endings,
            max_chars,
        )

    return words_to_text(query_words)


def _extend_query_tail(
    core: list[WordToken],
    next_words: list[WordToken],
    max_borrow: int,
    endings: str,
    max_chars: int,
) -> list[WordToken]:
    if not core or not next_words:
        return core
    text = words_to_text(core)
    if _ends_with_sentence(text, endings) or len(text) > max_chars:
        return core

    extended = list(core)
    borrowed = 0
    for word in next_words:
        if borrowed >= max_borrow:
            break
        extended.append(word)
        borrowed += 1
        if _ends_with_sentence(words_to_text(extended), endings):
            break
        if len(words_to_text(extended)) > max_chars:
            extended.pop()
            break
    return extended


def _extend_query_head(
    core: list[WordToken],
    prev_words: list[WordToken],
    max_borrow: int,
    endings: str,
    max_chars: int,
) -> list[WordToken]:
    if not core or not prev_words:
        return core

    prepended: list[WordToken] = []
    for word in reversed(prev_words):
        if len(prepended) >= max_borrow:
            break
        prepended.insert(0, word)
        if len(words_to_text(prepended + core)) > max_chars:
            prepended.pop(0)
            break
        if prepended and _ends_with_sentence(words_to_text(prepended), endings):
            break
    return prepended + core


def _pass_tail_borrow(
    windows: list[WindowWords],
    endings: str,
    max_borrow: int,
    max_chars: int,
) -> None:
    for index in range(len(windows)):
        current = windows[index]
        text = words_to_text(current.words)
        if not text or _ends_with_sentence(text, endings) or len(text) > max_chars:
            continue
        if index + 1 >= len(windows):
            continue
        _borrow_forward(current, windows[index + 1], max_borrow, endings, max_chars)


def _pass_fill_short(
    windows: list[WindowWords],
    endings: str,
    max_borrow: int,
    min_chars: int,
    max_chars: int,
) -> None:
    for index in range(len(windows)):
        current = windows[index]
        text = words_to_text(current.words)
        if not text or len(text) >= min_chars or len(text) > max_chars:
            continue
        if _ends_with_sentence(text, endings):
            continue
        if index + 1 < len(windows):
            _borrow_forward(current, windows[index + 1], max_borrow, endings, max_chars)


def _borrow_forward(
    target: WindowWords,
    source: WindowWords,
    max_borrow: int,
    endings: str,
    max_chars: int,
) -> None:
    borrowed = 0
    while borrowed < max_borrow and source.words:
        if len(words_to_text(target.words)) > max_chars:
            break
        word = source.words.pop(0)
        target.words.append(word)
        borrowed += 1
        if _ends_with_sentence(words_to_text(target.words), endings):
            break


def _ends_with_sentence(text: str, endings: str) -> bool:
    stripped = text.rstrip()
    if not stripped:
        return False
    return stripped[-1] in endings

