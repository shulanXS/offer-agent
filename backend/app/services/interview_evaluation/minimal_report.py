"""规则版最小评估报告（06 小步 1，无 LLM 能力评分）。"""
from __future__ import annotations

from typing import Any

from app.services.interview.memory.signal_map import all_plan_topic_ids, find_plan_topic
from app.services.interview_evaluation.candidate_report import build_candidate_review

EVALUATION_REPORT_VERSION = 2
EVALUATION_SOURCE_RULE_MINIMAL = "rule_minimal"


def build_minimal_evaluation_report(
    *,
    plan_json: dict[str, Any],
    configuration: dict[str, Any],
    runtime_state: dict[str, Any],
    evaluation_context: dict[str, Any],
    language: str = "en",
) -> dict[str, Any]:
    topics = plan_json.get("topics") or []
    total_topic_count = len(topics)
    completed_topic_ids = list(runtime_state.get("completed_topic_ids") or [])
    completed_topic_count = len(completed_topic_ids)

    evidence_by_topic = evaluation_context.get("evidence_by_topic") or {}
    topics_with_evidence_count = sum(
        1
        for topic_id in all_plan_topic_ids(plan_json)
        if (evidence_by_topic.get(topic_id) or {}).get("evidence")
    )

    coverage_rate = round(completed_topic_count / total_topic_count, 2) if total_topic_count else 0.0
    evidence_ratio = round(topics_with_evidence_count / total_topic_count, 2) if total_topic_count else 0.0
    overall_confidence = round(min(0.92, 0.35 + coverage_rate * 0.35 + evidence_ratio * 0.22), 2)

    strengths = _build_strengths(plan_json=plan_json, evidence_by_topic=evidence_by_topic)
    risks = _normalize_risk_lines(evaluation_context.get("risks") or [])
    unverified_items = _normalize_unverified_items(evaluation_context.get("unverified_items") or [])
    candidate_review = build_candidate_review(
        competencies=[],
        question_reviews=[],
        practice_recommendations=[],
        overall_score=None,
        risks=risks,
        unverified_items=unverified_items,
        configuration=configuration,
        strengths=strengths,
        completed_topic_count=completed_topic_count,
        total_topic_count=total_topic_count,
        plan_json=plan_json,
    )
    summary = str(candidate_review.get("summary") or "").strip()

    return {
        "version": EVALUATION_REPORT_VERSION,
        "source": EVALUATION_SOURCE_RULE_MINIMAL,
        "report_language": language,
        "summary": summary,
        "candidate_review": candidate_review,
        "overall_score": None,
        "coverage_rate": coverage_rate,
        "overall_confidence": overall_confidence,
        "coverage": {
            "completed_topic_count": completed_topic_count,
            "total_topic_count": total_topic_count,
            "topics_with_evidence_count": topics_with_evidence_count,
            "scored_topic_count": 0,
        },
        "competencies": [],
        "jd_match": None,
        "question_reviews": [],
        "practice_recommendations": [],
        "strengths": strengths,
        "risks": risks,
        "unverified_items": unverified_items,
        "model_info": None,
    }


def _build_strengths(*, plan_json: dict[str, Any], evidence_by_topic: dict[str, Any]) -> list[str]:
    strengths: list[str] = []
    for topic_id in all_plan_topic_ids(plan_json):
        bucket = evidence_by_topic.get(topic_id) or {}
        topic = find_plan_topic(plan_json, topic_id)
        topic_name = str((topic or {}).get("name") or topic_id)
        for item in bucket.get("evidence") or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("polarity", "")) != "positive":
                continue
            quote = str(item.get("quote", "")).strip()
            signal = str(item.get("matched_signal", "")).strip()
            if not quote:
                continue
            label = f"{topic_name}：{signal} — {quote}" if signal else f"{topic_name}：{quote}"
            strengths.append(label)
            if len(strengths) >= 4:
                return strengths
    if not strengths and evidence_by_topic:
        strengths.append("已记录部分回答要点，可在后续版本中查看更完整的能力评分。")
    return strengths


def _normalize_risk_lines(risks: list[Any]) -> list[str]:
    normalized: list[str] = []
    for item in risks:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = str(item.get("description") or item.get("content") or "").strip()
        else:
            text = ""
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _normalize_unverified_items(items: list[Any]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or item.get("description") or "").strip()
        if not content:
            continue
        entry = {"content": content}
        topic_id = str(item.get("topic_id", "")).strip()
        if topic_id:
            entry["topic_id"] = topic_id
        normalized.append(entry)
    return normalized


def _build_summary(
    *,
    interview_type: str,
    completed_topic_count: int,
    total_topic_count: int,
    topics_with_evidence_count: int,
    strengths_count: int,
    risks_count: int,
    unverified_count: int,
) -> str:
    audience = "校招" if interview_type == "campus" else "社招"
    if total_topic_count == 0:
        return "本场暂无可用计划主题，尚未形成有效评估摘要。"

    parts = [
        f"这是本场{audience}模拟面试的结构化摘要（规则版，置信度有限）。",
        f"计划共 {total_topic_count} 个主题，已完成 {completed_topic_count} 个，"
        f"其中 {topics_with_evidence_count} 个主题有可引用证据。",
    ]
    if strengths_count:
        parts.append(f"已提炼 {strengths_count} 条优势要点。")
    if risks_count:
        parts.append(f"识别 {risks_count} 项需要留意的风险。")
    if unverified_count:
        parts.append(f"另有 {unverified_count} 项尚未验证，未将其判为低分。")
    elif topics_with_evidence_count < completed_topic_count:
        parts.append("部分已覆盖主题证据仍不足，正式能力评分将在下一步接入。")
    return "".join(parts)
