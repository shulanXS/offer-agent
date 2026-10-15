"""学习档案读取：练前推荐与评估页长期行动。"""
from __future__ import annotations

from typing import Any

from app.db.store import Store
from app.services.interview_configuration_service import configuration_labels
from app.services.learning.aggregate import build_practice_cross_session_hints
from app.services.learning.planning_hints import build_planning_hints
from app.services.learning.schema import REPEAT_WEAK_THRESHOLD
from app.services.learning.eligibility import filter_eligible_outcome_rows
from app.services.learning.session_comparison import build_session_comparison
from app.services.learning.session_summary import is_eligible_learning_outcome


def _profile_key_parts(
    *,
    user_id: int,
    resume_id: str,
    target_role: str,
    interview_type: str,
) -> tuple[int, str, str, str] | None:
    resume_id = resume_id.strip()
    target_role = target_role.strip()
    interview_type = interview_type.strip()
    if not resume_id or not target_role or not interview_type:
        return None
    store = Store()
    if not store.get_resume(user_id, resume_id):
        return None
    return user_id, resume_id, target_role, interview_type


def get_learning_recommendations(
    *,
    user_id: int,
    resume_id: str,
    target_role: str,
    interview_type: str,
) -> dict[str, Any]:
    key = _profile_key_parts(
        user_id=user_id,
        resume_id=resume_id,
        target_role=target_role,
        interview_type=interview_type,
    )
    if not key:
        return _empty_recommendations()

    store = Store()
    profile_row = store.get_learning_profile(*key)
    if not profile_row:
        return _empty_recommendations()

    profile = profile_row.get("profile_json") or {}
    repeat_weak_signals = list(profile.get("repeat_weak_signals") or [])
    session_count = int(profile.get("session_count") or 0)
    has_learning_profile = session_count >= 1
    recommendations_available = bool(repeat_weak_signals)

    return {
        "has_learning_profile": has_learning_profile,
        "recommendations_available": recommendations_available,
        "session_count": session_count,
        "repeat_weak_signals": repeat_weak_signals if recommendations_available else [],
        "improved_signals": list(profile.get("improved_signals") or []),
        "planning_hints": build_planning_hints(repeat_weak_signals) if recommendations_available else "",
    }


def get_learning_context_for_session(*, user_id: int, session_id: str) -> dict[str, Any]:
    store = Store()
    record = store.get_interview_session_record(user_id, session_id)
    if not record:
        return _empty_learning_context()

    configuration = record.get("configuration") or {}
    resume_id = str(record.get("resume_id") or configuration.get("resume_id") or "").strip()
    target_role = str(configuration.get("target_role") or record.get("target_role") or "").strip()
    interview_type = str(configuration.get("interview_type") or "").strip()
    key = _profile_key_parts(
        user_id=user_id,
        resume_id=resume_id,
        target_role=target_role,
        interview_type=interview_type,
    )
    if not key:
        return _empty_learning_context()

    profile_row = store.get_learning_profile(*key)
    if not profile_row:
        return _empty_learning_context()

    profile = profile_row.get("profile_json") or {}
    labels = configuration_labels(configuration)
    current_outcome_row = store.get_learning_outcome_by_session(session_id)
    current_outcome = current_outcome_row.get("outcome_json") if current_outcome_row else None

    repeat_weak_signals = list(profile.get("repeat_weak_signals") or [])
    improved_signals = list(profile.get("improved_signals") or [])

    outcomes = store.list_learning_outcomes(
        user_id=user_id,
        resume_id=resume_id,
        target_role=target_role,
        interview_type=interview_type,
    )
    eligible_rows = filter_eligible_outcome_rows(
        store=store,
        user_id=user_id,
        outcome_rows=outcomes,
    )
    session_count = len(eligible_rows)
    ordered_outcomes = [item["outcome_json"] for item in eligible_rows]
    previous_outcome = None
    if (
        current_outcome
        and is_eligible_learning_outcome(current_outcome)
        and str(record.get("status", "")) == "completed"
        and len(ordered_outcomes) >= 2
    ):
        for index, outcome in enumerate(ordered_outcomes):
            if str(outcome.get("session_id", "")) == session_id and index > 0:
                previous_outcome = ordered_outcomes[index - 1]
                break

    session_comparison = (
        build_session_comparison(
            current_outcome=current_outcome,
            previous_outcome=previous_outcome,
        )
        if current_outcome
        and is_eligible_learning_outcome(current_outcome)
        and previous_outcome
        else None
    )
    cross_session_available = session_count >= 2 and bool(session_comparison)

    # 2.4：取出最近一场的 overall_score；只有存在上半场（已完成且 eligible）时返回。
    previous_overall_score: float | None = None
    if previous_outcome is not None:
        try:
            prev_score = previous_outcome.get("overall_score")
            if prev_score is not None:
                previous_overall_score = float(prev_score)
        except (TypeError, ValueError):
            previous_overall_score = None

    return {
        "has_learning_profile": session_count >= 1,
        "session_count": session_count,
        "target_role": target_role,
        "target_role_label": labels.get("target_role_label", target_role),
        "interview_type": interview_type,
        "interview_type_label": labels.get("interview_type_label", interview_type),
        "repeat_weak_signals": [],
        "improved_signals": [],
        "session_comparison": session_comparison,
        "cross_session_available": cross_session_available,
        "practice_cross_session_hints": build_practice_cross_session_hints(
            profile=profile,
            current_outcome=current_outcome,
        ),
        "repeat_weak_threshold": REPEAT_WEAK_THRESHOLD,
        "previous_overall_score": previous_overall_score,
    }


def _empty_recommendations() -> dict[str, Any]:
    return {
        "has_learning_profile": False,
        "recommendations_available": False,
        "session_count": 0,
        "repeat_weak_signals": [],
        "improved_signals": [],
        "planning_hints": "",
    }


def _empty_learning_context() -> dict[str, Any]:
    return {
        "has_learning_profile": False,
        "session_count": 0,
        "target_role": "",
        "target_role_label": "",
        "interview_type": "",
        "interview_type_label": "",
        "repeat_weak_signals": [],
        "improved_signals": [],
        "session_comparison": None,
        "cross_session_available": False,
        "practice_cross_session_hints": [],
        "repeat_weak_threshold": REPEAT_WEAK_THRESHOLD,
        "previous_overall_score": None,
    }
