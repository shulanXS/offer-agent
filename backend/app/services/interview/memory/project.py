"""working_memory → evidence_by_topic 投影（06 消费）。"""
from __future__ import annotations

from typing import Any

from app.services.interview.memory.merge import EVIDENCE_COVERAGE_MIN_STRENGTH, covered_signals_for_topic
from app.services.interview.memory.schema import ensure_working_memory
from app.services.interview.memory.signal_map import all_plan_topic_ids, find_plan_topic, plan_signals_for_topic


def _unverified_contradictions(working_memory: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in (working_memory.get("contradictions") or [])
        if isinstance(item, dict) and str(item.get("status", "unverified")) == "unverified"
    ]


def project_evaluation_memory(
    *,
    plan_json: dict[str, Any],
    working_memory: dict[str, Any],
) -> dict[str, Any]:
    memory = ensure_working_memory({"working_memory": working_memory})
    evidence = memory.get("evidence") or []
    claims = memory.get("claims") or []

    evidence_by_topic: dict[str, dict[str, Any]] = {}
    for topic_id in all_plan_topic_ids(plan_json):
        topic = find_plan_topic(plan_json, topic_id)
        if not topic:
            continue
        expected_signals = plan_signals_for_topic(topic)
        covered = sorted(covered_signals_for_topic(evidence, topic_id))
        missing = [signal for signal in expected_signals if signal not in set(covered)]
        topic_evidence = [item for item in evidence if str(item.get("topic_id", "")) == topic_id]
        evidence_by_topic[topic_id] = {
            "evidence": topic_evidence,
            "covered_signals": covered,
            "missing_signals": missing,
        }

    unverified_items = [
        item for item in claims if isinstance(item, dict) and str(item.get("status", "unverified")) == "unverified"
    ]
    contradictions = _unverified_contradictions(memory)
    combined_risks = list(memory.get("risks") or [])
    for item in contradictions:
        description = str(item.get("description", "")).strip()
        if description and description not in combined_risks:
            combined_risks.append(description)
    return {
        "evidence_by_topic": evidence_by_topic,
        "risks": combined_risks,
        "contradictions": contradictions,
        "unverified_items": unverified_items,
        "evaluation_anchors": [],
        "coverage_threshold": EVIDENCE_COVERAGE_MIN_STRENGTH,
    }
