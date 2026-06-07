"""Planning 预览：将落库计划转换为 API 响应（主题摘要、版本历史、generation_meta）。"""
from typing import Any

from app.core.constants import InterviewPlanSessionStatus
from app.services.interview_configuration_service import INTERVIEW_TYPES, LANGUAGES, TARGET_LEVELS, TARGET_ROLES
from app.services.interview_planning.constants import MAX_REGENERATIONS


def build_plan_preview(
    *,
    session_id: str,
    plan_record: dict[str, Any],
    configuration: dict[str, Any],
    status: str,
) -> dict[str, Any]:
    plan_json = plan_record["plan_json"]
    candidate_summary_json = plan_record["candidate_summary_json"]
    labels = _configuration_labels(configuration)

    return {
        "session_id": session_id,
        "status": status,
        "plan_id": plan_record["id"],
        "plan_version": plan_record["version"],
        "candidate_summary": {
            **labels,
            "duration_minutes": configuration["duration_minutes"],
            "focus_topics": candidate_summary_json.get("focus_topics", configuration["focus_topics"]),
            "reference_summary": candidate_summary_json.get("reference_summary", []),
            "has_jd": bool(configuration.get("jd_text", "").strip()),
        },
        "topics_preview": [
            {
                "id": topic["id"],
                "name": topic["name"],
                "required": topic["required"],
                "estimated_minutes": topic["estimated_minutes"],
            }
            for topic in plan_json.get("topics", [])
        ],
        "regenerations_remaining": _regenerations_remaining(plan_record["version"], status),
        "generation_meta": _extract_generation_meta(plan_json),
    }


def _extract_generation_meta(plan_json: dict[str, Any]) -> dict[str, Any] | None:
    meta = plan_json.get("generation_meta")
    if not isinstance(meta, dict):
        return None
    return {
        "source": str(meta.get("source", "unknown")),
        "generation_attempts": int(meta.get("generation_attempts", 0) or 0),
        "degraded": bool(meta.get("degraded", False)),
        "degraded_reason": meta.get("degraded_reason"),
    }


def build_version_history_item(
    *,
    plan_record: dict[str, Any],
    configuration: dict[str, Any],
) -> dict[str, Any]:
    preview = build_plan_preview(
        session_id=plan_record["session_id"],
        plan_record=plan_record,
        configuration=configuration,
        status="plan_ready",
    )
    return {
        "plan_id": plan_record["id"],
        "plan_version": plan_record["version"],
        "created_at": plan_record["created_at"],
        "regeneration_strategy": plan_record.get("regeneration_strategy"),
        "topics_preview": preview["topics_preview"],
        "reference_summary": preview["candidate_summary"]["reference_summary"],
    }


def _regenerations_remaining(plan_version: int, status: str) -> int:
    if status == InterviewPlanSessionStatus.PLAN_CONFIRMED.value:
        return 0
    return max(0, MAX_REGENERATIONS - (plan_version - 1))


def _configuration_labels(configuration: dict[str, Any]) -> dict[str, str]:
    lookup = {
        "interview_type": {item["value"]: item["label"] for item in INTERVIEW_TYPES},
        "target_role": {item["value"]: item["label"] for item in TARGET_ROLES},
        "language": {item["value"]: item["label"] for item in LANGUAGES},
        "target_level": {item["value"]: item["label"] for item in TARGET_LEVELS},
    }
    result: dict[str, str] = {}
    for field in ("interview_type", "target_role", "language", "target_level"):
        value = configuration[field]
        result[field] = value
        result[f"{field}_label"] = lookup[field].get(value, value)
    return result
