"""Interview Reply 图状态（小步 6B）。"""
from __future__ import annotations

from typing import Any, TypedDict


class InterviewReplyState(TypedDict, total=False):
    trace_id: str
    plan_json: dict[str, Any]
    configuration: dict[str, Any]
    resume: dict[str, Any] | None
    runtime_state: dict[str, Any]
    current_topic: dict[str, Any]
    all_messages: list[dict[str, Any]]
    latest_answer: str
    current_topic_id: str
    interview_type: str
    topic_messages: list[dict[str, Any]]
    following_topic: dict[str, Any] | None
    has_next_topic: bool
    observe_context: dict[str, Any]
    memory_context: dict[str, Any]
    extraction_result: dict[str, Any]
    boundary: dict[str, Any]
    decision: dict[str, Any]
    assistant_content: str
    assistant_kind: str
    assistant_meta: dict[str, Any]
    next_status: str
    # v1.1: 面试语言（en|zh），由 configuration.interview_language 注入
    interview_language: str
    # v3 1.4：ingest 阶段 precheck 命中硬边界时，service 端应跳过 user_message 写。
    _skip_user_message: bool


def build_interview_reply_state(
    *,
    trace_id: str,
    plan_json: dict[str, Any],
    configuration: dict[str, Any],
    resume: dict[str, Any] | None,
    runtime_state: dict[str, Any],
    current_topic: dict[str, Any],
    all_messages: list[dict[str, Any]],
    latest_answer: str,
) -> InterviewReplyState:
    # v1.1: 透传 interview_language 到 graph state
    interview_language = str(configuration.get("interview_language") or "en")
    return {
        "trace_id": trace_id,
        "plan_json": plan_json,
        "configuration": configuration,
        "resume": resume,
        "runtime_state": runtime_state,
        "current_topic": current_topic,
        "all_messages": all_messages,
        "latest_answer": latest_answer,
        "interview_language": interview_language,
    }
