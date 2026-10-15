"""追问话术生成与运行状态更新。"""
from __future__ import annotations

from app.agent.interview.nodes._agents import act_agent
from app.agent.interview.state import InterviewReplyState
from app.services.interview.constants import INTERVIEW_PHASE_TOPIC_FOLLOW_UP


def act_probe_node(state: InterviewReplyState) -> InterviewReplyState:
    decision = state["decision"]
    current_topic = state["current_topic"]
    current_topic_id = state["current_topic_id"]
    runtime_state = dict(state["runtime_state"])
    trace_id = state.get("trace_id", "")

    assistant_content = act_agent.generate_message(
        decision=decision,
        topic=current_topic,
        next_topic=None,
        topic_messages=state.get("topic_messages") or [],
        latest_answer=state["latest_answer"],
        interview_type=state["interview_type"],
        last_action=str(runtime_state.get("last_action") or ""),
        trace_id=trace_id,
        interview_language=state.get("interview_language") or "en",
    )
    expected_information = decision.get("expected_information") or []
    runtime_state["current_topic_probe_count"] = int(runtime_state.get("current_topic_probe_count") or 0) + 1
    runtime_state["last_probed_information"] = (
        str(expected_information[0]) if expected_information else str(decision.get("reason", ""))
    )
    runtime_state["last_action"] = str(decision["action"])
    runtime_state["phase"] = INTERVIEW_PHASE_TOPIC_FOLLOW_UP

    return {
        **state,
        "runtime_state": runtime_state,
        "assistant_content": assistant_content,
        "assistant_kind": "follow_up",
        "assistant_meta": {
            "topic_id": current_topic_id,
            "action": decision["action"],
            "trace_id": trace_id,
            "is_follow_up": True,
            "decision_reason": decision.get("reason", ""),
        },
        "next_status": "active",
    }
