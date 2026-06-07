"""Observe 上下文组装；05 小步 1 填充工作记忆占位与体积控制。"""
from __future__ import annotations

from typing import Any

from app.services.interview.context_limits import estimate_context_chars, trim_topic_messages
from app.services.interview.memory.schema import ensure_working_memory


def get_interview_memory_context(
    *,
    session_id: str,
    topic_id: str,
    trace_id: str = "",
    runtime_state: dict[str, Any] | None = None,
    topic_summaries: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """05 接入点。小步 1 从 runtime_state.working_memory 填充 relevant_memory 占位。"""
    _ = session_id, trace_id
    state = runtime_state or {}
    working_memory = ensure_working_memory(state)
    summaries = topic_summaries if topic_summaries is not None else (state.get("topic_summaries") or {})

    covered_signals: list[str] = []
    recent_evidence: list[dict[str, Any]] = []
    for item in working_memory.get("evidence") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("topic_id", "")) != str(topic_id):
            continue
        signal = str(item.get("matched_signal", "")).strip()
        if signal and signal not in covered_signals:
            covered_signals.append(signal)
        recent_evidence.append(item)

    topic_missing = [
        item
        for item in (working_memory.get("missing_information") or [])
        if isinstance(item, dict) and str(item.get("topic_id", "")) == str(topic_id)
    ]

    return {
        "relevant_memory": {
            "current_topic_id": topic_id,
            "covered_signals": covered_signals,
            "recent_evidence": recent_evidence[:5],
            "completed_topic_summary_ids": list(summaries.keys()),
        },
        "missing_information": topic_missing,
        "risks": list(working_memory.get("risks") or []),
        "contradictions": list(working_memory.get("contradictions") or []),
        "interview_knowledge": [],
    }


def build_observe_context(
    *,
    plan_json: dict[str, Any],
    configuration: dict[str, Any],
    resume: dict[str, Any] | None,
    runtime_state: dict[str, Any],
    topic_messages: list[dict[str, Any]],
    latest_answer: str = "",
    memory_context: dict[str, Any] | None = None,
    session_id: str = "",
    trace_id: str = "",
) -> dict[str, Any]:
    current_topic_id = str(runtime_state.get("current_topic_id", ""))
    current_topic = _find_topic(plan_json, current_topic_id)
    topic_summaries = runtime_state.get("topic_summaries") or {}
    context_topic_messages = trim_topic_messages(topic_messages)
    resolved_memory = memory_context or get_interview_memory_context(
        session_id=session_id,
        topic_id=current_topic_id,
        trace_id=trace_id,
        runtime_state=runtime_state,
        topic_summaries=topic_summaries,
    )
    return {
        "plan_json": plan_json,
        "configuration": configuration,
        "resume": resume or {},
        "runtime_state": runtime_state,
        "current_topic": current_topic,
        "topic_messages": topic_messages,
        "context_topic_messages": context_topic_messages,
        "topic_summaries": topic_summaries,
        "latest_answer": latest_answer,
        "memory_context": resolved_memory,
        "context_char_estimate": estimate_context_chars(
            topic_messages=context_topic_messages,
            topic_summaries=topic_summaries,
        ),
    }


def _find_topic(plan_json: dict[str, Any], topic_id: str) -> dict[str, Any] | None:
    for topic in plan_json.get("topics") or []:
        if str(topic.get("id")) == str(topic_id):
            return topic
    return None
