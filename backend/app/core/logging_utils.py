import json
import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import settings


FILE_LOGGER_NAMES = ("uvicorn.error", "uvicorn.access", "offer_agent")

# C1：PII 脱敏正则
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_CN_PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_CN_ID_RE = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
_BANK_CARD_RE = re.compile(r"(?<!\d)\d{16,19}(?!\d)")


def redact_pii(text: str) -> str:
    """对文本中的 PII 做最小化脱敏。"""
    if not text:
        return text
    text = _EMAIL_RE.sub("<email>", text)
    text = _CN_PHONE_RE.sub("<phone>", text)
    text = _CN_ID_RE.sub("<id_card>", text)
    text = _BANK_CARD_RE.sub("<bank_card>", text)
    return text


def setup_logging() -> None:
    log_file = settings.log_file
    log_file.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    for logger_name in FILE_LOGGER_NAMES:
        logger = logging.getLogger(logger_name)
        logger.setLevel(_resolve_level(settings.log_level))
        if _has_file_handler(logger, log_file):
            continue
        handler = RotatingFileHandler(
            log_file,
            maxBytes=settings.log_max_bytes,
            backupCount=settings.log_backup_count,
            encoding="utf-8",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)


def new_trace_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def log_payload(
    logger: logging.Logger,
    level: int,
    title: str,
    payload: Any,
    *,
    trace_id: str = "",
) -> None:
    prefix = f"[trace_id={trace_id}] " if trace_id else ""
    logger.log(level, "%s%s\n%s", prefix, title, _serialize_payload(payload))


def _serialize_payload(payload: Any) -> str:
    if isinstance(payload, str):
        content = payload
    else:
        try:
            content = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        except TypeError:
            content = str(payload)
    # C1：脱敏 + 截断
    content = redact_pii(content)
    if settings.log_payload_max_chars > 0 and len(content) > settings.log_payload_max_chars:
        return f"{content[:settings.log_payload_max_chars]}\n... [truncated]"
    return content


def _resolve_level(value: str) -> int:
    normalized = value.strip().upper()
    return getattr(logging, normalized, logging.INFO)


def _has_file_handler(logger: logging.Logger, log_file: Path) -> bool:
    target = str(log_file.resolve())
    for handler in logger.handlers:
        if isinstance(handler, RotatingFileHandler) and Path(handler.baseFilename).resolve().as_posix() == Path(target).as_posix():
            return True
    return False
