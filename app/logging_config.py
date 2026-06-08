from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config.settings import Settings, get_settings

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
NOISY_LOGGERS = ("httpx", "httpcore")
UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")


def _running_under_pytest() -> bool:
    import sys

    return "pytest" in sys.modules


def setup_logging(settings: Settings | None = None, *, force_file: bool = False) -> Path:
    settings = settings or get_settings()

    log_dir = Path(settings.log_dir)
    if not log_dir.is_absolute():
        log_dir = Path.cwd() / log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = (log_dir / settings.log_file).resolve()

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    formatter = logging.Formatter(LOG_FORMAT)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
        delay=False,
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    if force_file or not _running_under_pytest():
        root.addHandler(file_handler)
        _attach_app_file_handler(file_handler, level)

    if settings.log_console or _running_under_pytest():
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        console.setLevel(logging.WARNING)
        root.addHandler(console)

    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    for name in UVICORN_LOGGERS:
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
        uvicorn_logger.setLevel(level)

    logging.getLogger(__name__).info("logging configured file=%s console=%s", log_path, settings.log_console)
    return log_path


def _attach_app_file_handler(file_handler: RotatingFileHandler, level: int) -> None:
    """为 app.* 日志单独挂载文件 handler，避免 uvicorn 重置 root 后业务日志丢失。"""
    app_logger = logging.getLogger("app")
    app_logger.setLevel(level)
    app_logger.propagate = False
    for handler in list(app_logger.handlers):
        if isinstance(handler, RotatingFileHandler):
            app_logger.removeHandler(handler)
    app_logger.addHandler(file_handler)
