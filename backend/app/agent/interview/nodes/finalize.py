"""切题、正常结束与强制结束。"""
from __future__ import annotations

from app.agent.interview.nodes._agents import act_agent
from app.agent.interview.state import InterviewReplyState
from app.agent.interview.transitions import build_completion_message, build_early_finish_message
from app.services.interview.constants import INTERVIEW_PHASE_TOPIC_QUESTION
from app.services.interview.topic_summary import build_topic_summary


def _mark_topic_completed(state: InterviewReplyState) -> dict:
    current_topic = state["current_topic"]
    current_topic_id = state["current_topic_id"]
    runtime_state = dict(state["runtime_state"])

    summaries = dict(runtime_state.get("topic_summaries") or {})
    summaries[current_topic_id] = build_topic_summary(
        topic=current_topic,
        user_answer=state["latest_answer"],
        topic_messages=state.get("topic_messages") or [],
        trace_id=state.get("trace_id", ""),
    )
    runtime_state["topic_summaries"] = summaries

    completed_ids = list(runtime_state.get("completed_topic_ids") or [])
    if current_topic_id not in completed_ids:
        completed_ids.append(current_topic_id)
    runtime_state["completed_topic_ids"] = completed_ids
    return runtime_state


def finalize_advance_node(state: InterviewReplyState) -> InterviewReplyState:
    decision = state["decision"]
    current_topic = state["current_topic"]
    current_topic_id = state["current_topic_id"]
    following = state.get("following_topic")
    runtime_state = _mark_topic_completed(state)
    trace_id = state.get("trace_id", "")

    if following is not None:
        assistant_content = act_agent.generate_message(
            decision=decision,
            topic=current_topic,
            next_topic=following,
            topic_messages=[],
            latest_answer=state["latest_answer"],
            interview_type=state["interview_type"],
            trace_id=trace_id,
        )
        runtime_state["current_topic_id"] = str(following["id"])
        runtime_state["current_topic_round"] = 0
        runtime_state["current_topic_probe_count"] = 0
        runtime_state["last_probed_information"] = ""
        runtime_state["last_action"] = "next_topic"
        runtime_state["phase"] = INTERVIEW_PHASE_TOPIC_QUESTION
        return {
            **state,
            "runtime_state": runtime_state,
            "assistant_content": assistant_content,
            "assistant_kind": "question",
            "assistant_meta": {
                "topic_id": following["id"],
                "action": "next_topic",
                "trace_id": trace_id,
                "is_follow_up": False,
                "source_opening_question": str(following.get("opening_question", "")),
                "decision_reason": decision.get("reason", ""),
            },
            "next_status": "active",
        }

    assistant_content = build_completion_message(topic_count=len(state["plan_json"].get("topics") or []))
    runtime_state["last_action"] = "finish"
    runtime_state["finish_reason"] = "interview_completed"
    return {
        **state,
        "runtime_state": runtime_state,
        "assistant_content": assistant_content,
        "assistant_kind": "closing",
        "assistant_meta": {
            "topic_id": current_topic_id,
            "action": "finish",
            "trace_id": trace_id,
            "is_follow_up": False,
            "decision_reason": decision.get("reason", ""),
        },
        "next_status": "evaluating",
    }


def finalize_forced_finish_node(state: InterviewReplyState) -> InterviewReplyState:
    boundary = state.get("boundary") or {}
    reason = str(boundary.get("reason") or "")
    current_topic_id = state["current_topic_id"]
    trace_id = state.get("trace_id", "")
    runtime_state = _mark_topic_completed(state)
    runtime_state["last_action"] = "finish"
    runtime_state["finish_reason"] = reason or "forced_finish"

    return {
        **state,
        "runtime_state": runtime_state,
        "assistant_content": build_early_finish_message(reason=reason),
        "assistant_kind": "closing",
        "assistant_meta": {
            "topic_id": current_topic_id,
            "action": "finish",
            "trace_id": trace_id,
            "is_follow_up": False,
            "decision_reason": reason,
            "forced_finish": True,
        },
        "next_status": "evaluating",
        "decision": {
            "action": "finish",
            "reason": reason,
            "expected_information": [],
            "should_change_topic": True,
        },
    }
