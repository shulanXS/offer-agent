"""组装 Observe 上下文（含 05 记忆接口占位）。"""
from __future__ import annotations

from app.agent.interview.state import InterviewReplyState
from app.services.interview.context import build_observe_context


def build_observe_node(state: InterviewReplyState) -> InterviewReplyState:
    observe_context = build_observe_context(
        plan_json=state["plan_json"],
        configuration=state["configuration"],
        resume=state.get("resume"),
        runtime_state=state["runtime_state"],
        topic_messages=state.get("topic_messages") or [],
        latest_answer=state["latest_answer"],
        trace_id=state.get("trace_id", ""),
    )
    return {
        **state,
        "observe_context": observe_context,
        "memory_context": observe_context.get("memory_context") or {},
    }
