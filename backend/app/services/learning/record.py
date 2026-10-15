"""评估落库后写入跨场次 outcome 并更新 profile。"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from app.db.store import Store
from app.services.interview_evaluation.context import build_evaluation_context
from app.services.learning.aggregate import aggregate_profile, build_outcome_snapshot
from app.services.learning.eligibility import filter_eligible_outcome_rows
from app.services.learning.session_summary import is_eligible_learning_outcome


logger = logging.getLogger("uvicorn.error")


def record_session_outcome(*, user_id: int, session_id: str) -> dict[str, Any] | None:
    store = Store()
    record = store.get_interview_session_record(user_id, session_id)
    if not record:
        return None
    if str(record.get("status", "")) != "completed":
        return None

    evaluation = record.get("evaluation")
    if not isinstance(evaluation, dict):
        return None

    configuration = record.get("configuration") or {}
    resume_id = str(record.get("resume_id") or configuration.get("resume_id") or "").strip()
    target_role = str(configuration.get("target_role") or record.get("target_role") or "").strip()
    interview_type = str(configuration.get("interview_type") or "").strip()
    if not resume_id or not target_role or not interview_type:
        return None

    confirmed_plan_id = record.get("confirmed_plan_id")
    if not confirmed_plan_id:
        return None
    plan_record = store.get_plan_by_id(str(confirmed_plan_id))
    if not plan_record:
        return None

    started = time.perf_counter()
    evaluation_context = build_evaluation_context(
        plan_json=plan_record["plan_json"],
        configuration=configuration,
        runtime_state=record.get("workflow_state") or {},
        messages=record.get("messages") or [],
    )
    completed_at = str(record.get("updated_at") or "")
    outcome_snapshot = build_outcome_snapshot(
        session_id=session_id,
        completed_at=completed_at,
        plan_json=plan_record["plan_json"],
        evaluation=evaluation,
        evidence_by_topic=evaluation_context.get("evidence_by_topic") or {},
    )

    if not is_eligible_learning_outcome(outcome_snapshot):
        if store.get_learning_outcome_by_session(session_id):
            store.delete_learning_outcome(session_id)
    elif store.get_learning_outcome_by_session(session_id):
        store.update_learning_outcome(session_id, outcome_json=outcome_snapshot, completed_at=completed_at)
    else:
        store.insert_learning_outcome(
            outcome_id=str(uuid.uuid4()),
            user_id=user_id,
            resume_id=resume_id,
            session_id=session_id,
            target_role=target_role,
            interview_type=interview_type,
            completed_at=completed_at,
            outcome_json=outcome_snapshot,
        )

    outcomes = store.list_learning_outcomes(
        user_id=user_id,
        resume_id=resume_id,
        target_role=target_role,
        interview_type=interview_type,
    )
    eligible_outcomes = filter_eligible_outcome_rows(
        store=store,
        user_id=user_id,
        outcome_rows=outcomes,
    )
    # 3.4：评估完成时检查"已 decrement 但无 outcome"孤儿 → 触发补偿
    store.audit_outcome_for_session(session_id, reason="evaluation_completed")
    profile_json = aggregate_profile([item["outcome_json"] for item in eligible_outcomes])
    store.upsert_learning_profile(
        user_id=user_id,
        resume_id=resume_id,
        target_role=target_role,
        interview_type=interview_type,
        profile_json=profile_json,
    )

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "record_session_outcome completed: session_id=%s session_count=%s elapsed_ms=%s",
        session_id,
        profile_json.get("session_count"),
        elapsed_ms,
    )
    return profile_json
