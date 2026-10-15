"""证据驱动评估报告组装（06 小步 2）。"""
from __future__ import annotations

from typing import Any

from app.agent.interview_evaluation.agent import EvaluationAgent
from app.services.interview.memory.signal_map import all_plan_topic_ids
from app.services.interview_evaluation.aggregate import (
    compute_overall_confidence,
    compute_overall_score,
    count_discussed_topics,
    count_scored_topics,
)
from app.services.interview_evaluation.candidate_report import (
    build_candidate_review,
    enrich_competencies_for_candidate,
)
from app.services.interview_evaluation.competencies import derive_competencies
from app.services.interview_evaluation.jd_match import build_jd_match
from app.services.interview_evaluation.practice_recommendations import build_practice_recommendations
from app.services.interview_evaluation.question_reviews import build_question_reviews, validate_question_reviews
from app.services.interview_evaluation.minimal_report import (
    EVALUATION_REPORT_VERSION,
    _build_strengths,
    _normalize_risk_lines,
    _normalize_unverified_items,
)

EVALUATION_SOURCE_EVIDENCE = "evidence_rule"
EVALUATION_SOURCE_AGENT = "agent_enriched"


def build_evidence_driven_report(
    *,
    plan_json: dict[str, Any],
    configuration: dict[str, Any],
    runtime_state: dict[str, Any],
    evaluation_context: dict[str, Any],
    trace_id: str = "",
    use_agent: bool = True,
    language: str = "en",
) -> dict[str, Any]:
    competencies = derive_competencies(
        plan_json=plan_json,
        evaluation_context=evaluation_context,
        runtime_state=runtime_state,
    )
    validate_competencies(competencies, plan_json=plan_json)

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
    overall_score = compute_overall_score(competencies)
    scored_topic_count = count_scored_topics(competencies)
    discussed_topic_count = count_discussed_topics(
        competencies,
        completed_topic_count=completed_topic_count,
        scored_topic_count=scored_topic_count,
    )
    overall_confidence = compute_overall_confidence(
        competencies=competencies,
        coverage_rate=coverage_rate,
        evidence_ratio=evidence_ratio,
    )

    risks = _normalize_risk_lines(evaluation_context.get("risks") or [])
    unverified_items = _normalize_unverified_items(evaluation_context.get("unverified_items") or [])
    strengths = _build_strengths(plan_json=plan_json, evidence_by_topic=evidence_by_topic)

    source = EVALUATION_SOURCE_EVIDENCE
    model_info = None
    agent_comments: dict[str, str] = {}
    agent_narrative: dict[str, Any] | None = None
    if use_agent:
        agent = EvaluationAgent()
        agent_narrative, model_info = agent.enrich_narrative(
            evaluation_context=evaluation_context,
            competencies=competencies,
            plan_json=plan_json,
            trace_id=trace_id,
        )
        if agent_narrative:
            agent_comments = {
                str(item.get("topic_id", "")): str(item.get("evaluation_comment", "")).strip()
                for item in agent_narrative.get("competency_narratives") or []
                if str(item.get("evaluation_comment", "")).strip()
            }
            source = EVALUATION_SOURCE_AGENT

    jd_match = build_jd_match(
        configuration=configuration,
        plan_json=plan_json,
        evaluation_context=evaluation_context,
        competencies=competencies,
    )
    question_reviews = build_question_reviews(
        plan_json=plan_json,
        evaluation_context=evaluation_context,
        competencies=competencies,
        runtime_state=runtime_state,
    )
    validate_question_reviews(question_reviews, plan_json=plan_json)
    practice_recommendations = build_practice_recommendations(
        plan_json=plan_json,
        competencies=competencies,
        question_reviews=question_reviews,
    )

    candidate_review = build_candidate_review(
        competencies=competencies,
        question_reviews=question_reviews,
        practice_recommendations=practice_recommendations,
        overall_score=overall_score,
        risks=risks,
        unverified_items=unverified_items,
        configuration=configuration,
        completed_topic_count=completed_topic_count,
        total_topic_count=total_topic_count,
        scored_topic_count=scored_topic_count,
        discussed_topic_count=discussed_topic_count,
        plan_json=plan_json,
    )
    if agent_narrative and agent_narrative.get("candidate_review"):
        candidate_review = _merge_candidate_review(candidate_review, agent_narrative["candidate_review"])

    competencies = enrich_competencies_for_candidate(
        competencies,
        question_reviews=question_reviews,
        agent_comments=agent_comments,
    )
    summary = str(candidate_review.get("summary") or "").strip()

    return {
        "version": EVALUATION_REPORT_VERSION,
        "source": source,
        "report_language": language,
        "summary": summary,
        "candidate_review": candidate_review,
        "overall_score": overall_score,
        "overall_score_label": (
            "已评考察点均分" if (overall_score is not None and scored_topic_count >= 2)
            else "评分点不足"
        ),
        "coverage_rate": coverage_rate,
        "overall_confidence": overall_confidence,
        "coverage": {
            "completed_topic_count": completed_topic_count,
            "total_topic_count": total_topic_count,
            "topics_with_evidence_count": topics_with_evidence_count,
            "scored_topic_count": scored_topic_count,
            "discussed_topic_count": discussed_topic_count,
        },
        "competencies": competencies,
        "jd_match": jd_match,
        "question_reviews": question_reviews,
        "practice_recommendations": practice_recommendations,
        "strengths": strengths,
        "risks": risks,
        "unverified_items": unverified_items,
        "model_info": model_info,
    }


def validate_competencies(competencies: list[dict[str, Any]], *, plan_json: dict[str, Any]) -> None:
    plan_topics = plan_json.get("topics") or []
    if len(competencies) != len(plan_topics):
        raise ValueError("competencies 数量必须与 plan 主题一致")

    for index, competency in enumerate(competencies):
        topic = plan_topics[index]
        topic_id = str(topic.get("id", ""))
        if str(competency.get("topic_id", "")) != topic_id:
            raise ValueError(f"competency topic_id 不匹配: {competency.get('topic_id')}")
        if str(competency.get("name", "")) != str(topic.get("name", "")):
            raise ValueError(f"competency name 不匹配: {topic_id}")
        if str(competency.get("dimension", "")) != str(topic.get("dimension", "")):
            raise ValueError(f"competency dimension 不匹配: {topic_id}")

        status = str(competency.get("status", ""))
        score = competency.get("score")
        if status == "unverified" and score is not None:
            raise ValueError(f"unverified 能力不得有分数: {topic_id}")
        # 2.1：浮点分允许（1.0–5.0，0.5 步进）。
        if score is not None:
            score_value = float(score)
            if not (1.0 <= score_value <= 5.0):
                raise ValueError(f"score 超出范围: {topic_id}")

        confidence = float(competency.get("confidence") or 0)
        if confidence < 0 or confidence > 1:
            raise ValueError(f"confidence 超出范围: {topic_id}")

        for reference in competency.get("evidence_references") or []:
            if not isinstance(reference, dict):
                raise ValueError(f"evidence_references 结构非法: {topic_id}")
            quote = str(reference.get("quote", "")).strip()
            if not quote:
                raise ValueError(f"evidence_references.quote 不能为空: {topic_id}")


def _merge_candidate_review(base: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key in ("headline", "summary"):
        value = str(agent.get(key, "")).strip()
        if value:
            merged[key] = value
    for key in ("weaknesses", "suggestions", "highlights"):
        if key not in agent:
            continue
        values = agent.get(key)
        if isinstance(values, list):
            merged[key] = values
    return merged
