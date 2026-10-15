"""LLM 结构化决策 + 校验。"""
from __future__ import annotations

from app.agent.interview.nodes._agents import decide_agent
from app.agent.interview.state import InterviewReplyState
from app.services.interview.actions import normalize_decision


def decide_node(state: InterviewReplyState) -> InterviewReplyState:
    observe_context = state.get("observe_context") or {}
    topic_messages = observe_context.get("context_topic_messages")
    if not isinstance(topic_messages, list):
        topic_messages = state.get("topic_messages") or []
    runtime_state = dict(state["runtime_state"])
    raw_decision = decide_agent.decide(
        topic=state["current_topic"],
        topic_messages=topic_messages,
        topic_summaries=runtime_state.get("topic_summaries") or {},
        latest_answer=state["latest_answer"],
        runtime_state=runtime_state,
        has_next_topic=bool(state.get("has_next_topic")),
        memory_context=state.get("memory_context") or {},
        trace_id=state.get("trace_id", ""),
        interview_language=state.get("interview_language") or "en",
    )
    if raw_decision.get("_verify_contradiction"):
        runtime_state["contradiction_verification_used"] = True
    decision = normalize_decision(
        raw_decision,
        current_topic_id=state["current_topic_id"],
        has_next_topic=bool(state.get("has_next_topic")),
    )
    return {**state, "runtime_state": runtime_state, "decision": decision}
