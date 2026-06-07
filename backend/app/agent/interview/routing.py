"""Interview Reply 图条件边路由。"""
from __future__ import annotations

from typing import Literal

from app.agent.interview.state import InterviewReplyState
from app.services.interview.actions import PROBE_ACTIONS
from app.services.interview.boundaries import should_block_repeat_probe


def route_after_boundary(
    state: InterviewReplyState,
) -> Literal["finish", "next_topic", "continue"]:
    forced_action = (state.get("boundary") or {}).get("forced_action")
    if forced_action == "finish":
        return "finish"
    if forced_action == "next_topic":
        return "next_topic"
    return "continue"


def route_after_decide(
    state: InterviewReplyState,
) -> Literal["probe", "repeat_blocked", "advance"]:
    decision = state.get("decision") or {}
    action = str(decision.get("action", ""))
    if action in PROBE_ACTIONS or action in {"increase_difficulty", "decrease_difficulty"}:
        if should_block_repeat_probe(decision=decision, runtime_state=state["runtime_state"]):
            return "repeat_blocked"
        return "probe"
    return "advance"
