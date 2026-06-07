"""确定性边界检查。"""
from __future__ import annotations

from typing import Any

from app.agent.interview.state import InterviewReplyState
from app.services.interview.boundaries import evaluate_forced_action


def enforce_boundaries_node(state: InterviewReplyState) -> InterviewReplyState:
    current_topic_id = state["current_topic_id"]
    verdict = evaluate_forced_action(
        runtime_state=state["runtime_state"],
        plan_json=state["plan_json"],
        current_topic_id=current_topic_id,
    )
    boundary = {
        "forced_action": verdict.forced_action,
        "reason": verdict.reason,
    }
    updates: dict[str, Any] = {
        **state,
        "boundary": boundary,
    }
    if verdict.forced_action == "next_topic":
        updates["decision"] = {
            "action": "next_topic",
            "target_topic_id": current_topic_id,
            "reason": verdict.reason,
            "expected_information": [],
            "should_change_topic": True,
        }
    return updates
