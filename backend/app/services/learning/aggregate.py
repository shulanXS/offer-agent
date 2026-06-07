"""从 session outcomes 确定性聚合学习档案。"""
from __future__ import annotations

from typing import Any

from app.agent.interview_planning.validator import CAMPUS_DIMENSION_BUCKETS, EXPERIENCED_DIMENSION_BUCKETS
from app.services.learning.planning_hints import enrich_repeat_weak_signals
from app.services.learning.session_summary import build_session_summary
from app.services.learning.schema import (
    IMPROVED_SIGNAL_MAX_GROUPS,
    IMPROVED_STATUS_LABEL,
    PROFILE_VERSION,
    REPEAT_WEAK_THRESHOLD,
)
from app.services.interview.memory.signal_map import find_plan_topic


def build_outcome_snapshot(
    *,
    session_id: str,
    completed_at: str,
    plan_json: dict[str, Any],
    evaluation: dict[str, Any],
    evidence_by_topic: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    competencies = evaluation.get("competencies") or []
    topics: dict[str, dict[str, Any]] = {}
    for competency in competencies:
        if not isinstance(competency, dict):
            continue
        topic_id = str(competency.get("topic_id", "")).strip()
        if not topic_id:
            continue
        plan_topic = find_plan_topic(plan_json, topic_id) or {}
        bucket = evidence_by_topic.get(topic_id) or {}
        evidence = list(bucket.get("evidence") or [])
        status = str(competency.get("status", ""))
        discussed = bool(evidence) or status != "unverified"
        topics[topic_id] = {
            "topic_id": topic_id,
            "topic_name": str(competency.get("name") or plan_topic.get("name") or topic_id),
            "topic_dimension": str(competency.get("dimension") or plan_topic.get("dimension") or ""),
            "status": competency.get("status"),
            "score": competency.get("score"),
            "discussed": discussed,
            "covered_signals": list(bucket.get("covered_signals") or []),
            "missing_signals": list(bucket.get("missing_signals") or []),
        }
    session_summary = build_session_summary(
        plan_json=plan_json,
        evaluation=evaluation,
        topics=topics,
        evidence_by_topic=evidence_by_topic,
    )
    return {
        "session_id": session_id,
        "completed_at": completed_at,
        "topics": topics,
        "session_summary": session_summary,
    }


def aggregate_profile(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(outcomes, key=lambda item: str(item.get("completed_at", "")))
    session_count = len(ordered)

    signal_stats: dict[str, dict[str, Any]] = {}
    for outcome in ordered:
        session_id = str(outcome.get("session_id", ""))
        completed_at = str(outcome.get("completed_at", ""))
        topics = outcome.get("topics") or {}
        if not isinstance(topics, dict):
            continue
        for topic_data in topics.values():
            if not isinstance(topic_data, dict):
                continue
            if not topic_data.get("discussed"):
                continue
            dimension = str(topic_data.get("topic_dimension", "")).strip()
            for signal in topic_data.get("missing_signals") or []:
                text = str(signal).strip()
                if not text:
                    continue
                bucket = signal_stats.setdefault(
                    text,
                    {
                        "signal": text,
                        "topic_dimension": dimension,
                        "count": 0,
                        "last_session_id": session_id,
                        "last_completed_at": completed_at,
                    },
                )
                bucket["count"] += 1
                if completed_at >= str(bucket.get("last_completed_at", "")):
                    bucket["last_session_id"] = session_id
                    bucket["last_completed_at"] = completed_at
                    if dimension:
                        bucket["topic_dimension"] = dimension

    repeat_weak_signals = enrich_repeat_weak_signals(
        [
            {
                "signal": item["signal"],
                "topic_dimension": item.get("topic_dimension", ""),
                "count": item["count"],
                "last_session_id": item["last_session_id"],
            }
            for item in signal_stats.values()
            if int(item.get("count", 0)) >= REPEAT_WEAK_THRESHOLD
        ]
    )
    repeat_weak_signals.sort(key=lambda item: int(item.get("count", 0)), reverse=True)

    improved_signals = _build_improved_signals(ordered)

    topic_trend: list[dict[str, Any]] = []
    for outcome in ordered:
        topics = outcome.get("topics") or {}
        topic_trend.append(
            {
                "session_id": outcome.get("session_id"),
                "completed_at": outcome.get("completed_at"),
                "topics": {
                    topic_id: {
                        "status": topic_data.get("status"),
                        "score": topic_data.get("score"),
                        "discussed": topic_data.get("discussed"),
                        "missing_signals": list(topic_data.get("missing_signals") or []),
                    }
                    for topic_id, topic_data in topics.items()
                    if isinstance(topic_data, dict)
                },
            }
        )

    return {
        "version": PROFILE_VERSION,
        "session_count": session_count,
        "repeat_weak_signals": repeat_weak_signals,
        "improved_signals": improved_signals,
        "topic_trend": topic_trend,
    }


def build_practice_cross_session_hints(
    *,
    profile: dict[str, Any],
    current_outcome: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    repeat_map = {
        str(item.get("signal", "")).strip(): item
        for item in profile.get("repeat_weak_signals") or []
        if isinstance(item, dict)
    }
    if not repeat_map or not current_outcome:
        return []

    hints: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    topics = current_outcome.get("topics") or {}
    if not isinstance(topics, dict):
        return hints

    for topic_id, topic_data in topics.items():
        if not isinstance(topic_data, dict):
            continue
        if not topic_data.get("discussed"):
            continue
        for signal in topic_data.get("missing_signals") or []:
            text = str(signal).strip()
            stats = repeat_map.get(text)
            if not stats:
                continue
            count = int(stats.get("count", 0))
            if count < REPEAT_WEAK_THRESHOLD:
                continue
            key = (str(topic_id), text)
            if key in seen:
                continue
            seen.add(key)
            hints.append(
                {
                    "topic_id": str(topic_id),
                    "signal": text,
                    "repeat_count": count,
                    "hint": f"{text}在近 {count} 场中重复缺失",
                }
            )
    return hints


def _build_improved_signals(outcomes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(outcomes) < 2:
        return []

    latest = outcomes[-1]
    latest_dimension_views = _discussed_dimension_views(latest)
    if not latest_dimension_views:
        return []

    prior_missing_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for outcome in outcomes[:-1]:
        for dimension_key, view in _discussed_dimension_views(outcome).items():
            for signal in view["missing_signals"]:
                key = (dimension_key, signal)
                prior_missing_by_key.setdefault(
                    key,
                    {
                        "topic_dimension": view["topic_dimension"],
                        "topic_name": view["topic_name"],
                    },
                )

    grouped: dict[str, dict[str, Any]] = {}
    for (dimension_key, signal), meta in prior_missing_by_key.items():
        latest_view = latest_dimension_views.get(dimension_key)
        if not latest_view:
            continue
        if signal not in latest_view["expected_signals"]:
            continue
        if signal in latest_view["missing_signals"]:
            continue

        group = grouped.setdefault(
            dimension_key,
            {
                "topic_dimension": latest_view["topic_dimension"] or meta["topic_dimension"],
                "topic_name": latest_view["topic_name"] or meta["topic_name"],
                "signals": [],
                "status_label": IMPROVED_STATUS_LABEL,
            },
        )
        if signal not in group["signals"]:
            group["signals"].append(signal)

    improved = sorted(
        grouped.values(),
        key=lambda item: len(item.get("signals") or []),
        reverse=True,
    )
    return improved[:IMPROVED_SIGNAL_MAX_GROUPS]


def _discussed_dimension_views(outcome: dict[str, Any]) -> dict[str, dict[str, Any]]:
    views: dict[str, dict[str, Any]] = {}
    topics = outcome.get("topics") or {}
    if not isinstance(topics, dict):
        return views

    for topic_data in topics.values():
        if not isinstance(topic_data, dict) or not topic_data.get("discussed"):
            continue
        dimension = str(topic_data.get("topic_dimension", "")).strip()
        dimension_key = _dimension_key(dimension, topic_data)
        if not dimension_key:
            continue

        covered = {str(item).strip() for item in topic_data.get("covered_signals") or [] if str(item).strip()}
        missing = {str(item).strip() for item in topic_data.get("missing_signals") or [] if str(item).strip()}
        expected_signals = covered | missing
        if not expected_signals:
            continue

        current = views.get(dimension_key)
        if current is None:
            views[dimension_key] = {
                "topic_dimension": dimension,
                "topic_name": str(topic_data.get("topic_name", "")).strip(),
                "expected_signals": expected_signals,
                "missing_signals": missing,
            }
            continue

        current["expected_signals"] |= expected_signals
        current["missing_signals"] |= missing
        if not current["topic_name"]:
            current["topic_name"] = str(topic_data.get("topic_name", "")).strip()
        if not current["topic_dimension"]:
            current["topic_dimension"] = dimension
    return views


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
