"""记录本轮回答并准备主题上下文。"""
from __future__ import annotations

from app.agent.interview.state import InterviewReplyState
from app.services.interview.memory.schema import attach_working_memory_if_missing
from app.services.interview.runtime_state import next_topic as get_next_topic


def ingest_answer_node(state: InterviewReplyState) -> InterviewReplyState:
    current_topic = state["current_topic"]
    configuration = state["configuration"]
    runtime_state = attach_working_memory_if_missing(dict(state["runtime_state"]))
    current_topic_id = str(current_topic["id"])

    runtime_state["answer_round"] = int(runtime_state.get("answer_round") or 0) + 1
    runtime_state["current_topic_round"] = int(runtime_state.get("current_topic_round") or 0) + 1

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
