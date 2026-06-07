"""Evaluation Agent 输出校验（候选人可读报告）。"""
from __future__ import annotations

from typing import Any

from app.services.interview.memory.signal_map import all_plan_topic_ids
from app.services.interview_evaluation.feedback_items import normalize_feedback_list


class EvaluationAgentValidationError(ValueError):
    pass


def validate_agent_narrative(
    raw: Any,
    *,
    plan_json: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise EvaluationAgentValidationError("评估 Agent 输出必须是 JSON 对象")

    allowed_topic_ids = set(all_plan_topic_ids(plan_json))
    candidate_review = _normalize_candidate_review(raw.get("candidate_review"))
    if not candidate_review["summary"]:
        raise EvaluationAgentValidationError("candidate_review.summary 不能为空")

    narratives: list[dict[str, str]] = []
    for item in raw.get("competency_narratives") or []:
        if not isinstance(item, dict):
            continue
        topic_id = str(item.get("topic_id", "")).strip()
        if topic_id not in allowed_topic_ids:
            continue
        comment = str(item.get("evaluation_comment", "")).strip()
        if comment:
            narratives.append({"topic_id": topic_id, "evaluation_comment": comment})

    return {
        "candidate_review": candidate_review,
        "competency_narratives": narratives,
    }


def _normalize_candidate_review(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"headline": "", "summary": "", "highlights": [], "weaknesses": [], "suggestions": []}
    return {
        "headline": str(raw.get("headline", "")).strip(),
        "summary": str(raw.get("summary", "")).strip(),
        "highlights": normalize_feedback_list(raw.get("highlights"), limit=3),
        "weaknesses": normalize_feedback_list(raw.get("weaknesses"), limit=5),
        "suggestions": normalize_feedback_list(raw.get("suggestions"), limit=5),
    }
