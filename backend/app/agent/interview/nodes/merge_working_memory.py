"""工作记忆 merge 图节点。"""
from __future__ import annotations

from app.agent.interview.state import InterviewReplyState
from app.services.interview.context import get_interview_memory_context
from app.services.interview.memory.merge import merge_extraction_into_working_memory
from app.services.interview.memory.schema import ensure_working_memory


def merge_working_memory_node(state: InterviewReplyState) -> InterviewReplyState:
    runtime_state = dict(state["runtime_state"])
    current_topic_id = state["current_topic_id"]
    existing = ensure_working_memory(runtime_state)
    extraction = state.get("extraction_result")

    merged, _stats = merge_extraction_into_working_memory(
        working_memory=existing,
        extraction=extraction if isinstance(extraction, dict) else None,
        plan_json=state["plan_json"],
        current_topic_id=current_topic_id,
        trace_id=state.get("trace_id", ""),
    )
    runtime_state["working_memory"] = merged
    memory_context = get_interview_memory_context(
        session_id="",
        topic_id=current_topic_id,
        trace_id=state.get("trace_id", ""),
        runtime_state=runtime_state,
    )

    observe_context = dict(state.get("observe_context") or {})
    observe_context["memory_context"] = memory_context
    observe_context["runtime_state"] = runtime_state

    return {
        **state,
        "runtime_state": runtime_state,
        "memory_context": memory_context,
        "observe_context": observe_context,
    }
