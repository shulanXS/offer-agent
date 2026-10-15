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
    """B2：trim-mean + 覆盖权重。

    - 输入为 1-5 分的 competency
    - 不足 3 个有效分：直接平均（trim 无法生效）
    - 3 个及以上：去掉最高最低各 1 个后取平均，再映射到 0-100
    - 覆盖度低于 60% 时降权（乘以 0.8 + 0.2*覆盖率），不靠改 label 误导
    """
    scores = [int(item["score"]) for item in competencies if item.get("score") is not None]
    if not scores:
        return None
    total = len(competencies) or 1
    coverage = len(scores) / total

    if len(scores) >= 3:
        sorted_scores = sorted(scores)
        trimmed = sorted_scores[1:-1]
        avg5 = sum(trimmed) / len(trimmed)
    else:
        avg5 = sum(scores) / len(scores)

    score100 = avg5 / 5 * 100
    weighted = score100 * (0.8 + 0.2 * coverage)
    return int(round(weighted))


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
