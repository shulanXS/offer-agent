"""Observe / Decide 上下文体积控制（05 小步 1）。"""
from __future__ import annotations

from typing import Any

from app.core.config import settings


def _message_chars(message: dict[str, Any]) -> int:
    return len(str(message.get("content", "")))


def trim_topic_messages(
    messages: list[dict[str, Any]],
    *,
    max_messages: int | None = None,
    max_chars: int | None = None,
) -> list[dict[str, Any]]:
    if not messages:
        return []

    limit_messages = max_messages if max_messages is not None else settings.interview_context_max_messages
    limit_chars = max_chars if max_chars is not None else settings.interview_context_max_chars

    trimmed = list(messages)
    if limit_messages > 0 and len(trimmed) > limit_messages:
        trimmed = trimmed[-limit_messages:]

    if limit_chars <= 0:
        return trimmed

    while trimmed and sum(_message_chars(item) for item in trimmed) > limit_chars:
        trimmed = trimmed[1:]
    return trimmed


def estimate_context_chars(*, topic_messages: list[dict[str, Any]], topic_summaries: dict[str, Any]) -> int:
    message_chars = sum(_message_chars(item) for item in topic_messages)
    summary_chars = sum(len(str(value)) for value in topic_summaries.values())
    return message_chars + summary_chars
