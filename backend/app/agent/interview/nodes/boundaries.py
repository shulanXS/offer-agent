"""确定性边界检查。

v3：1.4 改造后，本节点保留"运行时再次校验"，若 ingest 阶段已经
通过 precheck 设了 forced_action，则原样使用。
"""
from __future__ import annotations

from typing import Any

from app.agent.interview.state import InterviewReplyState
from app.services.interview.boundaries import evaluate_forced_action


def enforce_boundaries_node(state: InterviewReplyState) -> InterviewReplyState:
    current_topic_id = state["current_topic_id"]
    existing = state.get("boundary") or {}
    if existing.get("forced_action"):
        # 1.4：precheck 路径已命中。保留 boundary / decision。
        return {**state, "boundary": existing}

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
