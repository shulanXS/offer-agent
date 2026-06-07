"""评估输入组装（06 小步 1）。"""
from __future__ import annotations

from typing import Any

from app.services.interview.memory.project import project_evaluation_memory
from app.services.interview.memory.schema import ensure_working_memory
from app.services.interview.memory.signal_map import all_plan_topic_ids


def group_messages_by_topic(
    messages: list[dict[str, Any]],
    *,
    plan_json: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {topic_id: [] for topic_id in all_plan_topic_ids(plan_json)}
    for message in messages:
        if not isinstance(message, dict):
            continue
        topic_id = str((message.get("meta") or {}).get("topic_id", "")).strip()
        if topic_id not in grouped:
            continue
        grouped[topic_id].append(message)
    return grouped


def build_evaluation_context(
    *,
    plan_json: dict[str, Any],
    configuration: dict[str, Any],
    runtime_state: dict[str, Any],
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    working_memory = ensure_working_memory(runtime_state)
    projected = project_evaluation_memory(plan_json=plan_json, working_memory=working_memory)
    jd_text = str(configuration.get("jd_text", "") or "").strip()
    return {
        "configuration": configuration,
        "confirmed_plan": plan_json,
        "messages_by_topic": group_messages_by_topic(messages, plan_json=plan_json),
        "evidence_by_topic": projected["evidence_by_topic"],
        "risks": projected["risks"],
        "unverified_items": projected["unverified_items"],
        "contradictions": projected.get("contradictions") or [],
        "evaluation_anchors": projected.get("evaluation_anchors") or [],
        "jd_text": jd_text,
        "structured_jd": None,
    }
