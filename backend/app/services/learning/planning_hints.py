"""练前推荐文案与 signal → focus_topic 映射。"""
from __future__ import annotations

from typing import Any

from app.services.interview_evaluation.practice_recommendations import (
    FOCUS_TOPIC_OPTIONS,
    map_topic_to_focus_topic,
)


def map_signal_to_focus_topic(*, signal: str, topic_dimension: str) -> str:
    mapped = map_topic_to_focus_topic(topic_name=signal, dimension=topic_dimension)
    if mapped in FOCUS_TOPIC_OPTIONS:
        return mapped
    return map_topic_to_focus_topic(topic_name=topic_dimension, dimension=signal)


def enrich_repeat_weak_signals(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for item in items:
        signal = str(item.get("signal", "")).strip()
        dimension = str(item.get("topic_dimension", "")).strip()
        if not signal:
            continue
        enriched.append(
            {
                **item,
                "suggested_focus_topic": map_signal_to_focus_topic(
                    signal=signal,
                    topic_dimension=dimension,
                ),
            }
        )
    return enriched


def build_planning_hints(repeat_weak_signals: list[dict[str, Any]]) -> str:
    if not repeat_weak_signals:
        return ""
    top = repeat_weak_signals[0]
    signal = str(top.get("signal", "")).strip()
    count = int(top.get("count", 0))
    if not signal or count < 2:
        return ""
    return f"多场模拟反复缺少{signal}，可纳入本场重点方向"
