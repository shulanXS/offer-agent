"""与上一场对比：场次级确定性对比点。"""
from __future__ import annotations

from typing import Any

from app.services.learning.schema import (
    COMPARISON_CHANGE_POINT_COUNT,
    COVERAGE_TOPIC_DELTA_THRESHOLD,
    PERFORMANCE_SCORE_DELTA_THRESHOLD,
    ROUNDS_DELTA_THRESHOLD,
    SIGNAL_COVERAGE_RATE_DELTA_THRESHOLD,
)
from app.services.learning.session_summary import derive_session_summary


def build_session_comparison(
    *,
    current_outcome: dict[str, Any],
    previous_outcome: dict[str, Any],
) -> dict[str, Any] | None:
    if not current_outcome or not previous_outcome:
        return None

    current = derive_session_summary(current_outcome)
    previous = derive_session_summary(previous_outcome)
    points = [
        _build_depth_point(current=current, previous=previous),
        _build_performance_point(current=current, previous=previous),
        _build_engagement_point(current=current, previous=previous),
    ][:COMPARISON_CHANGE_POINT_COUNT]

    return {
        "baseline_label": "上一场",
        "baseline_session_id": str(previous_outcome.get("session_id", "")),
        "baseline_completed_at": str(previous_outcome.get("completed_at", "")),
        "discussed_coverage": {
            "label": "已考察方向",
            "baseline_count": int(previous.get("discussed_topics") or 0),
            "current_count": int(current.get("discussed_topics") or 0),
        },
        "points": points,
        "summary_line": _build_summary_line(points),
    }


def _build_depth_point(*, current: dict[str, Any], previous: dict[str, Any]) -> dict[str, str]:
    current_discussed = int(current.get("discussed_topics") or 0)
    previous_discussed = int(previous.get("discussed_topics") or 0)
    if current_discussed <= 0 and previous_discussed <= 0:
        return _point(
            category="depth",
            tone="unavailable",
            headline="回答全面性",
            detail="",
        )

    current_depth = float(current.get("signal_coverage_rate") or 0)
    previous_depth = float(previous.get("signal_coverage_rate") or 0)
    depth_delta = current_depth - previous_depth
    if depth_delta >= SIGNAL_COVERAGE_RATE_DELTA_THRESHOLD:
        return _point(
            category="depth",
            tone="better",
            headline="回答更全面",
            detail=f"考察点覆盖率 {int(previous_depth * 100)}% → {int(current_depth * 100)}%",
        )
    if depth_delta <= -SIGNAL_COVERAGE_RATE_DELTA_THRESHOLD:
        return _point(
            category="depth",
            tone="worse",
            headline="回答不够全面",
            detail=f"考察点覆盖率 {int(previous_depth * 100)}% → {int(current_depth * 100)}%",
        )
    return _point(
        category="depth",
        tone="same",
        headline="全面性与上场接近",
        detail=f"覆盖率约 {int(current_depth * 100)}%",
    )


def _build_performance_point(*, current: dict[str, Any], previous: dict[str, Any]) -> dict[str, str]:
    current_scored = int(current.get("scored_topics") or 0)
    previous_scored = int(previous.get("scored_topics") or 0)
    current_score = current.get("overall_score")
    previous_score = previous.get("overall_score")
    if current_scored <= 0 or previous_scored <= 0 or current_score is None or previous_score is None:
        return _point(
            category="performance",
            tone="unavailable",
            headline="已评表现",
            detail="",
        )

    score_delta = int(current_score) - int(previous_score)
    if score_delta >= PERFORMANCE_SCORE_DELTA_THRESHOLD:
        return _point(
            category="performance",
            tone="better",
            headline="已评表现更好",
            detail=f"综合分 {previous_score} → {current_score}",
        )
    if score_delta <= -PERFORMANCE_SCORE_DELTA_THRESHOLD:
        return _point(
            category="performance",
            tone="worse",
            headline="已评表现偏弱",
            detail=f"综合分 {previous_score} → {current_score}",
        )
    return _point(
        category="performance",
        tone="same",
        headline="已评表现与上场接近",
        detail=f"综合分均为 {current_score}",
    )


def _build_engagement_point(*, current: dict[str, Any], previous: dict[str, Any]) -> dict[str, str]:
    current_rounds = int(current.get("user_answer_rounds") or 0)
    previous_rounds = int(previous.get("user_answer_rounds") or 0)
    if current_rounds <= 0 and previous_rounds <= 0:
        return _point(
            category="engagement",
            tone="unavailable",
            headline="互动投入",
            detail="",
        )

    rounds_delta = current_rounds - previous_rounds
    if rounds_delta >= ROUNDS_DELTA_THRESHOLD:
        return _point(
            category="engagement",
            tone="better",
            headline="互动更充分",
            detail=f"上场 {previous_rounds} 轮 → 本场 {current_rounds} 轮",
        )
    if rounds_delta <= -ROUNDS_DELTA_THRESHOLD:
        return _point(
            category="engagement",
            tone="worse",
            headline="互动偏少",
            detail=f"上场 {previous_rounds} 轮 → 本场 {current_rounds} 轮",
        )
    return _point(
        category="engagement",
        tone="same",
        headline="回答轮次与上场接近",
        detail=f"两场均为 {current_rounds} 轮" if current_rounds == previous_rounds else "",
    )


def _point(*, category: str, tone: str, headline: str, detail: str) -> dict[str, str]:
    return {
        "category": category,
        "tone": tone,
        "headline": headline,
        "detail": detail,
    }


def _build_summary_line(points: list[dict[str, Any]]) -> str:
    actionable = [item for item in points if item.get("tone") in {"better", "worse"}]
    if not actionable:
        return "相比上场：整体表现接近"

    better = [item for item in actionable if item.get("tone") == "better"]
    worse = [item for item in actionable if item.get("tone") == "worse"]
    if better and worse:
        return f"相比上场：{better[0]['headline']}，但{worse[0]['headline']}"
    if better:
        return f"相比上场：{better[0]['headline']}"
    return f"相比上场：{worse[0]['headline']}"
