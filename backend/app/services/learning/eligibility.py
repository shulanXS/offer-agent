"""学习档案场次有效性过滤。"""
from __future__ import annotations

from typing import Any

from app.db.store import Store
from app.services.learning.session_summary import is_eligible_learning_outcome


def filter_eligible_outcome_rows(
    *,
    store: Store,
    user_id: int,
    outcome_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    eligible: list[dict[str, Any]] = []
    for row in outcome_rows:
        outcome = row.get("outcome_json") or {}
        if not isinstance(outcome, dict) or not is_eligible_learning_outcome(outcome):
            continue
        session_id = str(outcome.get("session_id") or row.get("session_id") or "").strip()
        if not session_id:
            continue
        record = store.get_interview_session_record(user_id, session_id)
        if not record or str(record.get("status", "")) != "completed":
            continue
        eligible.append(row)
    return eligible


def filter_eligible_outcomes(outcome_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    eligible: list[dict[str, Any]] = []
    for row in outcome_rows:
        outcome = row.get("outcome_json") or {}
        if isinstance(outcome, dict) and is_eligible_learning_outcome(outcome):
            eligible.append(outcome)
    return eligible
