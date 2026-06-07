"""面试运行状态初始化与更新。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.services.interview.constants import (
    INTERVIEW_DURATION_MINUTES,
    INTERVIEW_PHASE_TOPIC_QUESTION,
    RUNTIME_SCHEMA_VERSION,
)
from app.services.interview.memory.schema import empty_working_memory


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_initial_runtime_state(
    *,
    trace_id: str,
    confirmed_plan_id: str,
    plan_json: dict[str, Any],
    interview_type: str,
) -> dict[str, Any]:
    topics = list(plan_json.get("topics") or [])
    if not topics:
        raise ValueError("plan has no topics")

    first_topic = topics[0]
    required_topic_ids = [str(item["id"]) for item in topics if item.get("required")]

    return {
        "schema_version": RUNTIME_SCHEMA_VERSION,
        "trace_id": trace_id,
        "confirmed_plan_id": confirmed_plan_id,
        "interview_clock_started": False,
        "current_topic_id": str(first_topic["id"]),
        "completed_topic_ids": [],
        "required_topic_ids": required_topic_ids,
        "interview_type": interview_type,
        "answer_round": 0,
        "current_topic_round": 0,
        "current_topic_probe_count": 0,
        "last_probed_information": "",
        "topic_summaries": {},
        "working_memory": empty_working_memory(),
        "last_action": "",
        "contradiction_verification_used": False,
        "phase": INTERVIEW_PHASE_TOPIC_QUESTION,
    }


def find_topic(plan_json: dict[str, Any], topic_id: str) -> dict[str, Any] | None:
    for topic in plan_json.get("topics") or []:
        if str(topic.get("id")) == str(topic_id):
            return topic
    return None


def find_topic_index(plan_json: dict[str, Any], topic_id: str) -> int:
    topics = plan_json.get("topics") or []
    for index, topic in enumerate(topics):
        if str(topic.get("id")) == str(topic_id):
            return index
    return -1


def next_topic(plan_json: dict[str, Any], current_topic_id: str) -> dict[str, Any] | None:
    topics = plan_json.get("topics") or []
    for index, topic in enumerate(topics):
        if str(topic.get("id")) == str(current_topic_id):
            if index + 1 < len(topics):
                return topics[index + 1]
            return None
    return None


def topic_name(plan_json: dict[str, Any], topic_id: str) -> str:
    topic = find_topic(plan_json, topic_id)
    return str(topic.get("name", "")).strip() if topic else ""


def total_topic_count(plan_json: dict[str, Any]) -> int:
    return len(plan_json.get("topics") or [])


def completed_topic_count(runtime_state: dict[str, Any]) -> int:
    return len(runtime_state.get("completed_topic_ids") or [])


def ensure_interview_clock_started(
    runtime_state: dict[str, Any],
    *,
    duration_minutes: int = INTERVIEW_DURATION_MINUTES,
) -> tuple[dict[str, Any], bool]:
    """进入正式面试页或首次作答时再启动倒计时，避免在计划页 activate 后空耗时长。"""
    state = dict(runtime_state)
    if state.get("deadline_at"):
        if not state.get("interview_clock_started"):
            state["interview_clock_started"] = True
        return state, False

    started_at = datetime.now(timezone.utc)
    state["interview_clock_started"] = True
    state["started_at"] = started_at.isoformat()
    state["deadline_at"] = (
        started_at + timedelta(minutes=duration_minutes)
    ).isoformat()
    return state, True
