"""域 6.1 结构化事件日志。

每个域关键路径发出 domain event（带 `event` 字段），便于 grep / 后续接入 OpenTelemetry。
"""
from __future__ import annotations

import logging
from typing import Any

# 关键事件名常量（统一管理，方便 grep）
INTERVIEW_ACTIVATE_COMMITTED = "interview.activate.committed"
INTERVIEW_ACTIVATE_ROLLED_BACK = "interview.activate.rolled_back"
REPLY_USER_MESSAGE_PERSISTED = "reply.user_message.persisted"
REPLY_ASSISTANT_MESSAGE_PERSISTED = "reply.assistant_message.persisted"
EVALUATION_COMPLETED = "evaluation.completed"
PLAN_CONFIRMED_ATOMIC = "plan.confirmed.atomic"
PLAN_CONFIRMED_FAILED = "plan.confirmed.failed"
QUOTA_DECREMENTED = "quota.decremented"
QUOTA_COMPENSATED = "quota.compensated"
RESUME_EXTRACTED = "resume.extracted"
RESUME_PARSE_FAILED = "resume.parse_failed"


def emit_event(
    logger: logging.Logger,
    event: str,
    payload: dict[str, Any] | None = None,
    *,
    level: int = logging.INFO,
) -> None:
    """发出一个 domain event。结构稳定：`event=xxx fields={...}`。"""
    logger.log(level, "event=%s fields=%s", event, payload or {})


def commit_event(
    logger: logging.Logger,
    event: str,
    *,
    trace_id: str = "",
    **fields: Any,
) -> None:
    """事务 commit 后调用。trace_id 自动加进 fields。"""
    payload = dict(fields)
    if trace_id:
        payload["trace_id"] = trace_id
    emit_event(logger, event, payload)


def rollback_event(
    logger: logging.Logger,
    event: str,
    *,
    trace_id: str = "",
    error: str = "",
    **fields: Any,
) -> None:
    """事务回滚时调用。level=ERROR。"""
    payload = dict(fields)
    if trace_id:
        payload["trace_id"] = trace_id
    if error:
        payload["error"] = error
    emit_event(logger, event, payload, level=logging.ERROR)
