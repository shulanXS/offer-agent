"""单场摘要：供跨场次对比使用。"""
from __future__ import annotations

from typing import Any

from app.agent.interview_planning.validator import CAMPUS_DIMENSION_BUCKETS, EXPERIENCED_DIMENSION_BUCKETS


def build_session_summary(
    *,
    plan_json: dict[str, Any],
    evaluation: dict[str, Any],
    topics: dict[str, dict[str, Any]],
    evidence_by_topic: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    competencies = evaluation.get("competencies") or []
    coverage = evaluation.get("coverage") or {}

    total_topics = len(topics) or int(coverage.get("total_topic_count") or 0)
    discussed_topics = sum(1 for item in topics.values() if item.get("discussed"))
    scored_topics = sum(1 for item in topics.values() if item.get("score") is not None)

    covered_total = 0
    missing_total = 0
    positive_evidence_count = 0
    negative_evidence_count = 0
    by_dimension: dict[str, dict[str, Any]] = {}

    for topic_id, topic_data in topics.items():
        if not topic_data.get("discussed"):
            continue
        bucket = evidence_by_topic.get(topic_id) or {}
        covered = [str(item).strip() for item in bucket.get("covered_signals") or [] if str(item).strip()]
        missing = [str(item).strip() for item in bucket.get("missing_signals") or [] if str(item).strip()]
        covered_total += len(covered)
        missing_total += len(missing)

        for item in bucket.get("evidence") or []:
            if not isinstance(item, dict):
                continue
            polarity = str(item.get("polarity", "")).strip()
            if polarity == "positive":
                positive_evidence_count += 1
            elif polarity == "negative":
                negative_evidence_count += 1

        dimension = str(topic_data.get("topic_dimension", "")).strip()
        dimension_key = _dimension_key(dimension, topic_data)
        if not dimension_key:
            continue
        entry = by_dimension.setdefault(
            dimension_key,
            {
                "dimension_key": dimension_key,
                "dimension_label": dimension or dimension_key,
                "discussed": 0,
                "scored": 0,
                "score_sum": 0,
                "covered_signals": 0,
                "missing_signals": 0,
            },
        )
        entry["discussed"] += 1
        score = topic_data.get("score")
        if isinstance(score, int):
            entry["scored"] += 1
            entry["score_sum"] += score
        entry["covered_signals"] += len(covered)
        entry["missing_signals"] += len(missing)
        if dimension and not entry.get("dimension_label"):
            entry["dimension_label"] = dimension

    signal_denominator = covered_total + missing_total
    signal_coverage_rate = round(covered_total / signal_denominator, 2) if signal_denominator else 0.0
    coverage_rate = round(discussed_topics / total_topics, 2) if total_topics else 0.0

    scored_scores = [
        int(item.get("score"))
        for item in topics.values()
        if isinstance(item.get("score"), int)
    ]
    avg_scored_competency = (
        round(sum(scored_scores) / len(scored_scores), 1) if scored_scores else None
    )

    user_answer_rounds = 0
    for competency in competencies:
        if not isinstance(competency, dict):
            continue
        user_answer_rounds += len(competency.get("answer_rounds") or [])

    dimension_summary: dict[str, dict[str, Any]] = {}
    for key, entry in by_dimension.items():
        dim_denominator = int(entry["covered_signals"]) + int(entry["missing_signals"])
        dimension_summary[key] = {
            "dimension_key": entry["dimension_key"],
            "dimension_label": entry["dimension_label"],
            "discussed": entry["discussed"],
            "scored": entry["scored"],
            "avg_score": (
                round(entry["score_sum"] / entry["scored"], 1)
                if entry["scored"]
                else None
            ),
            "signal_coverage": (
                round(entry["covered_signals"] / dim_denominator, 2)
                if dim_denominator
                else 0.0
            ),
        }

    return {
        "overall_score": evaluation.get("overall_score"),
        "total_topics": total_topics,
        "discussed_topics": discussed_topics,
        "scored_topics": scored_topics,
        "coverage_rate": coverage_rate,
        "signal_coverage_rate": signal_coverage_rate,
        "user_answer_rounds": user_answer_rounds,
        "avg_scored_competency": avg_scored_competency,
        "positive_evidence_count": positive_evidence_count,
        "negative_evidence_count": negative_evidence_count,
        "by_dimension": dimension_summary,
    }


def is_eligible_learning_outcome(outcome: dict[str, Any]) -> bool:
    """仅真正进行过面试的场次参与跨场学习与对比。"""
    summary = derive_session_summary(outcome)
    discussed = int(summary.get("discussed_topics") or 0)
    scored = int(summary.get("scored_topics") or 0)
    rounds = int(summary.get("user_answer_rounds") or 0)
    return discussed > 0 or scored > 0 or rounds > 0


def derive_session_summary(outcome: dict[str, Any]) -> dict[str, Any]:
    stored = outcome.get("session_summary")
    if isinstance(stored, dict) and any(
        stored.get(key) is not None
        for key in ("total_topics", "discussed_topics", "scored_topics", "signal_coverage_rate")
    ):
        return stored

    topics = outcome.get("topics") or {}
    if not isinstance(topics, dict):
        topics = {}

    discussed_topics = sum(1 for item in topics.values() if isinstance(item, dict) and item.get("discussed"))
    scored_topics = sum(1 for item in topics.values() if isinstance(item, dict) and item.get("score") is not None)
    total_topics = len(topics)

    covered_total = 0
    missing_total = 0
    scored_scores: list[int] = []
    user_answer_rounds = 0

    for topic_data in topics.values():
        if not isinstance(topic_data, dict) or not topic_data.get("discussed"):
            continue
        covered = [str(item).strip() for item in topic_data.get("covered_signals") or [] if str(item).strip()]
        missing = [str(item).strip() for item in topic_data.get("missing_signals") or [] if str(item).strip()]
        covered_total += len(covered)
        missing_total += len(missing)
        score = topic_data.get("score")
        if isinstance(score, int):
            scored_scores.append(score)

    signal_denominator = covered_total + missing_total
    return {
        "overall_score": None,
        "total_topics": total_topics,
        "discussed_topics": discussed_topics,
        "scored_topics": scored_topics,
        "coverage_rate": round(discussed_topics / total_topics, 2) if total_topics else 0.0,
        "signal_coverage_rate": round(covered_total / signal_denominator, 2) if signal_denominator else 0.0,
        "user_answer_rounds": user_answer_rounds,
        "avg_scored_competency": (
            round(sum(scored_scores) / len(scored_scores), 1) if scored_scores else None
        ),
        "positive_evidence_count": 0,
        "negative_evidence_count": 0,
        "by_dimension": {},
    }


def _dimension_key(dimension: str, topic_data: dict[str, Any]) -> str:
    haystack = " ".join(
        [
            dimension,
            str(topic_data.get("topic_name", "")),
        ]
    ).strip()
    if not haystack:
        return ""

    for buckets in (EXPERIENCED_DIMENSION_BUCKETS, CAMPUS_DIMENSION_BUCKETS):
        for bucket in buckets:
            if dimension == bucket["label"] or any(alias in haystack for alias in bucket["aliases"]):
                return str(bucket["id"])
    return dimension
