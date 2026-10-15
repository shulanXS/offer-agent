"""记录本轮回答并准备主题上下文。

v3 根因改造 1.4：precheck_boundary 在 ingest 之前检查"如果再答一轮是否触发硬边界"，
若命中则 `skip_user_message = True`，service 层不写 user_message，
直接走 finalize_* 路径。
"""
from __future__ import annotations

from typing import Any

from app.agent.interview.state import InterviewReplyState
from app.services.interview.boundaries import evaluate_forced_action
from app.services.interview.memory.schema import attach_working_memory_if_missing
from app.services.interview.runtime_state import next_topic as get_next_topic


def ingest_answer_node(state: InterviewReplyState) -> InterviewReplyState:
    current_topic = state["current_topic"]
    configuration = state["configuration"]
    runtime_state = attach_working_memory_if_missing(dict(state["runtime_state"]))
    current_topic_id = str(current_topic["id"])

    # 1.4：precheck 用"已经答完本轮之后"的 round 状态做边界判定。
    runtime_state["answer_round"] = int(runtime_state.get("answer_round") or 0) + 1
    runtime_state["current_topic_round"] = int(runtime_state.get("current_topic_round") or 0) + 1

    precheck = evaluate_forced_action(
        runtime_state=runtime_state,
        plan_json=state["plan_json"],
        current_topic_id=current_topic_id,
    )
    if precheck.forced_action:
        following = get_next_topic(state["plan_json"], current_topic_id)
        interview_type = str(
            configuration.get("interview_type") or runtime_state.get("interview_type") or "experienced"
        )
        boundary = {
            "forced_action": precheck.forced_action,
            "reason": precheck.reason,
        }
        decision: dict[str, Any] = {
            "action": precheck.forced_action,
            "target_topic_id": current_topic_id,
            "reason": precheck.reason,
            "expected_information": [],
            "should_change_topic": precheck.forced_action == "next_topic",
        }
        return {
            **state,
            "runtime_state": runtime_state,
            "current_topic_id": current_topic_id,
            "interview_type": interview_type,
            "following_topic": following,
            "has_next_topic": following is not None,
            "boundary": boundary,
            "decision": decision,
            "_skip_user_message": True,
        }

    topic_messages = [
        message
        for message in state["all_messages"]
        if str((message.get("meta") or {}).get("topic_id", "")) == current_topic_id
    ]
    following = get_next_topic(state["plan_json"], current_topic_id)
    interview_type = str(
        configuration.get("interview_type") or runtime_state.get("interview_type") or "experienced"
    )

    return {
        **state,
        "runtime_state": runtime_state,
        "current_topic_id": current_topic_id,
        "interview_type": interview_type,
        "topic_messages": topic_messages,
        "following_topic": following,
        "has_next_topic": following is not None,
    }
