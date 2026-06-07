"""动态面试会话详情序列化。"""
from __future__ import annotations

from typing import Any

from app.services.interview.boundaries import (
    is_wrap_up_zone,
    resolve_display_remaining_seconds,
)
from app.services.interview.constants import INTERVIEW_PHASE_TOPIC_QUESTION, MAX_ANSWER_ROUNDS
from app.services.interview.runtime_state import completed_topic_count, topic_name, total_topic_count


def build_topics_preview(plan_json: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(topic.get("id", "")),
            "name": str(topic.get("name", "")),
            "required": bool(topic.get("required")),
            "estimated_minutes": int(topic.get("estimated_minutes") or 0),
        }
        for topic in plan_json.get("topics") or []
    ]


def build_progress(
    *,
    plan_json: dict[str, Any],
    runtime_state: dict[str, Any],
    session_status: str = "active",
    session_updated_at: str | None = None,
) -> dict[str, Any]:
    current_topic_id = str(runtime_state.get("current_topic_id", ""))
    deadline_at = str(runtime_state.get("deadline_at") or "")
    remaining = resolve_display_remaining_seconds(
        deadline_at=deadline_at,
        runtime_state=runtime_state,
        session_status=session_status,
        session_updated_at=session_updated_at,
    )
    return {
        "current_topic_id": current_topic_id,
        "current_topic_name": topic_name(plan_json, current_topic_id),
        "completed_topic_count": completed_topic_count(runtime_state),
        "total_topic_count": total_topic_count(plan_json),
        "answer_round": int(runtime_state.get("answer_round") or 0),
        "max_answer_rounds": MAX_ANSWER_ROUNDS,
        "phase": str(runtime_state.get("phase") or INTERVIEW_PHASE_TOPIC_QUESTION),
        "deadline_at": deadline_at,
        "remaining_seconds": remaining,
        "is_wrap_up_zone": (
            is_wrap_up_zone(deadline_at) if session_status == "active" and deadline_at else False
        ),
        "is_reply_processing": bool(runtime_state.get("reply_in_progress")),
    }


def serialize_live_session_detail(
    *,
    session_row: dict[str, Any],
    configuration: dict[str, Any],
    plan_record: dict[str, Any],
    messages: list[dict[str, Any]],
    runtime_state: dict[str, Any],
) -> dict[str, Any]:
    plan_json = plan_record.get("plan_json") or {}
    status = session_row["status"]
    progress = None
    if status in {"active", "evaluating", "completed"} and runtime_state.get("current_topic_id"):
        progress = build_progress(
            plan_json=plan_json,
            runtime_state=runtime_state,
            session_status=status,
            session_updated_at=str(session_row.get("updated_at") or ""),
        )

    return {
        "id": session_row["id"],
        "title": session_row["title"],
        "target_role": session_row["target_role"],
        "status": status,
        "configuration": configuration,
        "confirmed_plan_id": session_row.get("confirmed_plan_id"),
        "topics_preview": build_topics_preview(plan_json),
        "messages": messages,
        "progress": progress,
        "created_at": session_row["created_at"],
        "updated_at": session_row["updated_at"],
    }
