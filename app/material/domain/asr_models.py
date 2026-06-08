from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

AsrTaskStatus = Literal["pending", "processing", "completed", "failed"]


@dataclass
class AsrSubmitResult:
    success: bool
    task_id: str = ""
    x_tt_logid: str = ""
    error: str = ""


@dataclass
class AsrQueryResult:
    success: bool
    status: AsrTaskStatus = "failed"
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""


@dataclass
class AsrRecognizeResult:
    """Final ASR result after submit + poll until completed."""

    success: bool
    task_id: str = ""
    x_tt_logid: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""
