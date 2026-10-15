"""域 6.1 验证：domain event 在 commit/rollback 路径上发出。"""
from __future__ import annotations

import logging

from app.core.events import (
    commit_event,
    emit_event,
    rollback_event,
    EVALUATION_COMPLETED,
    INTERVIEW_ACTIVATE_COMMITTED,
    INTERVIEW_ACTIVATE_ROLLED_BACK,
)


def test_emit_event_writes_event_prefix(caplog) -> None:
    logger = logging.getLogger("test_event_emit")
    with caplog.at_level(logging.INFO, logger="test_event_emit"):
        emit_event(logger, EVALUATION_COMPLETED, {"session_id": "abc"})
    record = next(r for r in caplog.records if r.name == "test_event_emit")
    assert record.levelname == "INFO"
    assert record.getMessage().startswith("event=")
    assert "evaluation.completed" in record.getMessage()
    assert "session_id" in record.getMessage()


def test_commit_event_includes_trace_id(caplog) -> None:
    logger = logging.getLogger("test_commit_event")
    with caplog.at_level(logging.INFO, logger="test_commit_event"):
        commit_event(
            logger,
            INTERVIEW_ACTIVATE_COMMITTED,
            trace_id="t-123",
            session_id="s-1",
            user_id=42,
        )
    record = next(r for r in caplog.records if r.name == "test_commit_event")
    assert "interview.activate.committed" in record.getMessage()
    assert "t-123" in record.getMessage()
    assert "s-1" in record.getMessage()
    assert "42" in record.getMessage()


def test_rollback_event_uses_error_level(caplog) -> None:
    logger = logging.getLogger("test_rollback_event")
    with caplog.at_level(logging.ERROR, logger="test_rollback_event"):
        rollback_event(
            logger,
            INTERVIEW_ACTIVATE_ROLLED_BACK,
            trace_id="t-1",
            session_id="s-1",
            error="quota_exhausted",
        )
    record = next(r for r in caplog.records if r.name == "test_rollback_event")
    assert record.levelname == "ERROR"
    assert "interview.activate.rolled_back" in record.getMessage()
    assert "quota_exhausted" in record.getMessage()


def test_event_names_are_stable() -> None:
    """事件名常量不应被无意修改。"""
    assert EVALUATION_COMPLETED == "evaluation.completed"
    assert INTERVIEW_ACTIVATE_COMMITTED == "interview.activate.committed"
    assert INTERVIEW_ACTIVATE_ROLLED_BACK == "interview.activate.rolled_back"
