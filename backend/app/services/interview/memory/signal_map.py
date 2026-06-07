"""plan 主题 signal 映射（05 专题）。"""
from __future__ import annotations

from typing import Any


def plan_signals_for_topic(topic: dict[str, Any]) -> list[str]:
    signals: list[str] = []
    for key in ("expected_signals", "focus_points"):
        for item in topic.get(key) or []:
            text = str(item).strip()
            if text and text not in signals:
                signals.append(text)
    return signals


def resolve_plan_signal(signal: str, topic: dict[str, Any]) -> str | None:
    token = str(signal).strip()
    if not token:
        return None
    for candidate in plan_signals_for_topic(topic):
        if candidate == token:
            return candidate
    return None


def find_plan_topic(plan_json: dict[str, Any], topic_id: str) -> dict[str, Any] | None:
    for topic in plan_json.get("topics") or []:
        if str(topic.get("id")) == str(topic_id):
            return topic
    return None


def is_valid_plan_topic_id(plan_json: dict[str, Any], topic_id: str) -> bool:
    return find_plan_topic(plan_json, topic_id) is not None


def all_plan_topic_ids(plan_json: dict[str, Any]) -> list[str]:
    return [str(topic.get("id", "")) for topic in plan_json.get("topics") or [] if topic.get("id")]
