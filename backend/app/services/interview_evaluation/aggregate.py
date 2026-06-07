"""评估聚合规则（06 小步 2）。"""
from __future__ import annotations

from typing import Any


def count_scored_topics(competencies: list[dict[str, Any]]) -> int:
    return sum(1 for item in competencies if item.get("score") is not None)


def count_discussed_topics(
    competencies: list[dict[str, Any]],
    *,
    completed_topic_count: int = 0,
    scored_topic_count: int = 0,
) -> int:
    """至少聊到的主题数：有证据/评分的方向（与考察覆盖列表一致，不含仅切换未展开的主题）。"""
    _ = completed_topic_count
    from_competencies = sum(
        1 for item in competencies if str(item.get("status", "")) != "unverified"
    )
    return max(from_competencies, scored_topic_count)


def is_partial_score_coverage(*, scored_topic_count: int, total_topic_count: int) -> bool:
    if total_topic_count <= 0:
        return False
    return scored_topic_count < total_topic_count


def compute_overall_score(competencies: list[dict[str, Any]]) -> int | None:
    scores = [item["score"] for item in competencies if item.get("score") is not None]
    if not scores:
        return None
    average = sum(scores) / len(scores)
    return int(round(average / 5 * 100))


def compute_overall_confidence(
    *,
    competencies: list[dict[str, Any]],
    coverage_rate: float,
    evidence_ratio: float,
) -> float:
    if not competencies:
        return round(min(0.92, 0.35 + coverage_rate * 0.35 + evidence_ratio * 0.22), 2)

    scored = [item for item in competencies if item.get("score") is not None]
    if scored:
        competency_confidence = sum(float(item.get("confidence") or 0) for item in scored) / len(scored)
    else:
        competency_confidence = 0.25

    blended = competency_confidence * 0.7 + coverage_rate * 0.18 + evidence_ratio * 0.12
    return round(min(0.95, blended), 2)
