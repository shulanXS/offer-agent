"""面试硬边界：时间、轮数、单主题与收尾区。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.services.interview.constants import (
    INTERVIEW_DURATION_MINUTES,
    INTERVIEW_WRAP_UP_MINUTES,
    MAX_ANSWER_ROUNDS,
    MAX_TOPIC_ANSWER_ROUNDS,
    MAX_TOPIC_PROBE_COUNT,
)
from app.services.interview.runtime_state import next_topic


@dataclass(frozen=True)
class BoundaryVerdict:
    forced_action: str | None
    reason: str = ""


def set_deadline_at(*, started_at: datetime, duration_minutes: int = INTERVIEW_DURATION_MINUTES) -> str:
    deadline = started_at.astimezone(timezone.utc) + timedelta(minutes=duration_minutes)
    return deadline.isoformat()


def parse_iso_datetime(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def remaining_seconds(deadline_at: str, *, now: datetime | None = None) -> int | None:
    deadline = parse_iso_datetime(deadline_at)
    if not deadline:
        return None
    current = now or datetime.now(timezone.utc)
    return max(0, int((deadline - current).total_seconds()))


def freeze_remaining_seconds(runtime_state: dict[str, Any]) -> dict[str, Any]:
    """结束面试时快照剩余秒数，避免 evaluating 后仍随 wall clock 递减。"""
    updated = dict(runtime_state)
    if updated.get("remaining_seconds_at_finish") is not None:
        return updated
    deadline_at = str(updated.get("deadline_at") or "")
    remaining = remaining_seconds(deadline_at)
    if remaining is not None:
        updated["remaining_seconds_at_finish"] = remaining
    return updated


def resolve_display_remaining_seconds(
    *,
    deadline_at: str,
    runtime_state: dict[str, Any],
    session_status: str,
    session_updated_at: str | None = None,
) -> int | None:
    if session_status == "active":
        if not deadline_at:
            return INTERVIEW_DURATION_MINUTES * 60
        return remaining_seconds(deadline_at)

    frozen = runtime_state.get("remaining_seconds_at_finish")
    if frozen is not None:
        return max(0, int(frozen))

    if session_updated_at:
        finished_at = parse_iso_datetime(session_updated_at)
        if finished_at:
            return remaining_seconds(deadline_at, now=finished_at)

    return remaining_seconds(deadline_at)


def is_past_deadline(deadline_at: str, *, now: datetime | None = None) -> bool:
    remaining = remaining_seconds(deadline_at, now=now)
    return remaining is not None and remaining <= 0


def is_wrap_up_zone(deadline_at: str, *, now: datetime | None = None) -> bool:
    remaining = remaining_seconds(deadline_at, now=now)
    if remaining is None:
        return False
    return remaining <= INTERVIEW_WRAP_UP_MINUTES * 60


def required_topics_covered(*, runtime_state: dict[str, Any], plan_json: dict[str, Any]) -> bool:
    required_ids = set(runtime_state.get("required_topic_ids") or [])
    if not required_ids:
        required_ids = {str(topic["id"]) for topic in plan_json.get("topics") or [] if topic.get("required")}
    completed = set(runtime_state.get("completed_topic_ids") or [])
    return required_ids.issubset(completed)


def evaluate_forced_action(
    *,
    runtime_state: dict[str, Any],
    plan_json: dict[str, Any],
    current_topic_id: str,
    now: datetime | None = None,
) -> BoundaryVerdict:
    deadline_at = str(runtime_state.get("deadline_at") or "")
    answer_round = int(runtime_state.get("answer_round") or 0)
    topic_round = int(runtime_state.get("current_topic_round") or 0)
    probe_count = int(runtime_state.get("current_topic_probe_count") or 0)

    if is_past_deadline(deadline_at, now=now):
        return BoundaryVerdict(forced_action="finish", reason="deadline_reached")

    if answer_round >= MAX_ANSWER_ROUNDS:
        return BoundaryVerdict(forced_action="finish", reason="max_answer_rounds")

    if is_wrap_up_zone(deadline_at, now=now):
        if required_topics_covered(runtime_state=runtime_state, plan_json=plan_json):
            return BoundaryVerdict(forced_action="finish", reason="wrap_up_required_topics_covered")
        following = next_topic(plan_json, current_topic_id)
        if following is None:
            return BoundaryVerdict(forced_action="finish", reason="wrap_up_no_more_topics")
        return BoundaryVerdict(forced_action="next_topic", reason="wrap_up_cover_required_topics")

    if topic_round >= MAX_TOPIC_ANSWER_ROUNDS:
        following = next_topic(plan_json, current_topic_id)
        if following is None:
            return BoundaryVerdict(forced_action="finish", reason="topic_round_limit_last_topic")
        return BoundaryVerdict(forced_action="next_topic", reason="topic_round_limit")

    if probe_count >= MAX_TOPIC_PROBE_COUNT:
        following = next_topic(plan_json, current_topic_id)
        if following is None:
            return BoundaryVerdict(forced_action="finish", reason="probe_limit_last_topic")
        return BoundaryVerdict(forced_action="next_topic", reason="probe_limit")

    return BoundaryVerdict(forced_action=None)


def should_block_repeat_probe(*, decision: dict[str, Any], runtime_state: dict[str, Any]) -> bool:
    expected = decision.get("expected_information") or []
    candidate = str(expected[0]).strip() if expected else str(decision.get("reason", "")).strip()
    last_probed = str(runtime_state.get("last_probed_information") or "").strip()
    if not candidate or not last_probed:
        return False
    return candidate == last_probed
