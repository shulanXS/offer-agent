"""会话状态机（A4）：集中定义合法状态与转换。"""
from __future__ import annotations

from enum import Enum

from app.core.errors import ErrorCode, raise_app_error


class SessionState(str, Enum):
    PLANNING = "planning"
    PLAN_READY = "plan_ready"
    PLAN_CONFIRMED = "plan_confirmed"
    ACTIVE = "active"
    EVALUATING = "evaluating"
    COMPLETED = "completed"


ALLOWED: dict[SessionState, set[SessionState]] = {
    SessionState.PLANNING: {SessionState.PLAN_READY},
    SessionState.PLAN_READY: {SessionState.PLAN_READY, SessionState.PLAN_CONFIRMED},
    SessionState.PLAN_CONFIRMED: {SessionState.ACTIVE},
    SessionState.ACTIVE: {SessionState.ACTIVE, SessionState.EVALUATING},
    SessionState.EVALUATING: {SessionState.COMPLETED},
    SessionState.COMPLETED: set(),
}


def coerce(value: str | SessionState) -> SessionState:
    """把字符串或 Enum 归一化；非法值抛 409。"""
    if isinstance(value, SessionState):
        return value
    if isinstance(value, str):
        for state in SessionState:
            if state.value == value:
                return state
    raise_app_error(409, ErrorCode.SESSION_NOT_ACTIVE, f"未知会话状态: {value!r}")


def assert_transition(from_state: str | SessionState, to_state: str | SessionState) -> None:
    """断言状态转换合法；非法抛 409。"""
    f = coerce(from_state)
    t = coerce(to_state)
    if t not in ALLOWED[f]:
        raise_app_error(
            409,
            ErrorCode.SESSION_NOT_ACTIVE,
            f"非法状态转换: {f.value} -> {t.value}",
        )
