"""工作记忆 merge 与覆盖判定（05 小步 2）。"""
from __future__ import annotations

import copy
import logging
from dataclasses import dataclass
from typing import Any

from app.services.interview.memory.contradictions import detect_potential_contradictions
from app.services.interview.memory.extraction_schema import ExtractionValidationStats
from app.services.interview.memory.schema import ensure_working_memory
from app.services.interview.memory.signal_map import all_plan_topic_ids, plan_signals_for_topic


logger = logging.getLogger("uvicorn.error")

EVIDENCE_COVERAGE_MIN_STRENGTH = 0.5


@dataclass
class MergeStats:
    merged_claims: int = 0
    merged_evidence: int = 0
    merged_risks: int = 0
    merged_contradictions: int = 0
    discarded_extraction_items: int = 0
    degraded: bool = False


def merge_extraction_into_working_memory(
    *,
    working_memory: dict[str, Any],
    extraction: dict[str, Any] | None,
    plan_json: dict[str, Any],
    current_topic_id: str,
    trace_id: str = "",
) -> tuple[dict[str, Any], MergeStats]:
    stats = MergeStats()
    base = ensure_working_memory({"working_memory": working_memory})
    if not extraction:
        stats.degraded = True
        synced = copy.deepcopy(base)
        synced["missing_information"] = recompute_missing_information(plan_json=plan_json, working_memory=synced)
        synced["covered_topics"], synced["uncovered_topics"] = recompute_topic_coverage(
            plan_json=plan_json,
            working_memory=synced,
        )
        return synced, stats

    merged = copy.deepcopy(base)
    merged["claims"] = _merge_claims(merged.get("claims") or [], extraction.get("claims") or [], stats)
    merged["evidence"] = _merge_evidence(merged.get("evidence") or [], extraction.get("evidence") or [], stats)
    merged["risks"] = _merge_risks(merged.get("risks") or [], extraction.get("risks") or [], stats)
    detected = detect_potential_contradictions(
        existing_memory=base,
        new_claims=extraction.get("claims") or [],
        new_evidence=extraction.get("evidence") or [],
        current_topic_id=current_topic_id,
    )
    incoming_contradictions = list(extraction.get("potential_contradictions") or []) + detected
    merged["contradictions"] = _merge_contradictions(
        merged.get("contradictions") or [],
        incoming_contradictions,
        stats,
    )
    merged["missing_information"] = recompute_missing_information(plan_json=plan_json, working_memory=merged)
    merged["covered_topics"], merged["uncovered_topics"] = recompute_topic_coverage(
        plan_json=plan_json,
        working_memory=merged,
    )

    logger.info(
        "[trace_id=%s] working_memory merged topic=%s claims=%d evidence=%d missing=%d risks=%d contradictions=%d",
        trace_id or "-",
        current_topic_id,
        len(merged.get("claims") or []),
        len(merged.get("evidence") or []),
        len(merged.get("missing_information") or []),
        len(merged.get("risks") or []),
        len(merged.get("contradictions") or []),
    )
    return merged, stats


def recompute_missing_information(*, plan_json: dict[str, Any], working_memory: dict[str, Any]) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []
    evidence = working_memory.get("evidence") or []
    for topic in plan_json.get("topics") or []:
        topic_id = str(topic.get("id", ""))
        if not topic_id:
            continue
        covered = covered_signals_for_topic(evidence, topic_id)
        for signal in plan_signals_for_topic(topic):
            if signal not in covered:
                missing.append({"topic_id": topic_id, "signal": signal, "from_plan": True})
    return missing


def recompute_topic_coverage(
    *,
    plan_json: dict[str, Any],
    working_memory: dict[str, Any],
) -> tuple[list[str], list[str]]:
    evidence = working_memory.get("evidence") or []
    covered_topics: list[str] = []
    uncovered_topics: list[str] = []
    for topic_id in all_plan_topic_ids(plan_json):
        topic = next((item for item in plan_json.get("topics") or [] if str(item.get("id")) == topic_id), None)
        if not topic:
            continue
        signals = plan_signals_for_topic(topic)
        covered = covered_signals_for_topic(evidence, topic_id)
        if signals and all(signal in covered for signal in signals):
            covered_topics.append(topic_id)
        elif signals:
            uncovered_topics.append(topic_id)
        elif covered:
            covered_topics.append(topic_id)
        else:
            uncovered_topics.append(topic_id)
    return covered_topics, uncovered_topics


def covered_signals_for_topic(
    evidence: list[dict[str, Any]],
    topic_id: str,
    *,
    min_strength: float = EVIDENCE_COVERAGE_MIN_STRENGTH,
) -> set[str]:
    covered: set[str] = set()
    for item in evidence:
        if not isinstance(item, dict):
            continue
        if str(item.get("topic_id", "")) != str(topic_id):
            continue
        signal = str(item.get("matched_signal", "")).strip()
        if not signal:
            continue
        try:
            strength = float(item.get("strength", 0))
        except (TypeError, ValueError):
            strength = 0.0
        if strength >= min_strength:
            covered.add(signal)
    return covered


def _merge_claims(existing: list[dict[str, Any]], incoming: list[dict[str, Any]], stats: MergeStats) -> list[dict[str, Any]]:
    merged = list(existing)
    seen = {_claim_key(item) for item in existing if isinstance(item, dict)}
    for item in incoming:
        if not isinstance(item, dict):
            stats.discarded_extraction_items += 1
            continue
        key = _claim_key(item)
        if key in seen:
            continue
        merged.append(item)
        seen.add(key)
        stats.merged_claims += 1
    return merged


def _merge_evidence(existing: list[dict[str, Any]], incoming: list[dict[str, Any]], stats: MergeStats) -> list[dict[str, Any]]:
    merged = list(existing)
    seen = {_evidence_key(item) for item in existing if isinstance(item, dict)}
    for item in incoming:
        if not isinstance(item, dict):
            stats.discarded_extraction_items += 1
            continue
        key = _evidence_key(item)
        if key in seen:
            continue
        merged.append(item)
        seen.add(key)
        stats.merged_evidence += 1
    return merged


def _merge_risks(existing: list[Any], incoming: list[Any], stats: MergeStats) -> list[str]:
    merged = [str(item).strip() for item in existing if str(item).strip()]
    seen = set(merged)
    for item in incoming:
        text = str(item).strip()
        if not text:
            stats.discarded_extraction_items += 1
            continue
        if text in seen:
            continue
        merged.append(text)
        seen.add(text)
        stats.merged_risks += 1
    return merged


def _merge_contradictions(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    stats: MergeStats,
) -> list[dict[str, Any]]:
    merged = list(existing)
    seen = {_contradiction_key(item) for item in existing if isinstance(item, dict)}
    for item in incoming:
        if not isinstance(item, dict):
            stats.discarded_extraction_items += 1
            continue
        key = _contradiction_key(item)
        if key in seen:
            continue
        merged.append(item)
        seen.add(key)
        stats.merged_contradictions += 1
    return merged


def _claim_key(item: dict[str, Any]) -> tuple[str, str]:
    return str(item.get("topic_id", "")), str(item.get("content", "")).strip()


def _evidence_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(item.get("topic_id", "")),
        str(item.get("matched_signal", "")).strip(),
        str(item.get("quote", "")).strip(),
    )


def _contradiction_key(item: dict[str, Any]) -> tuple[str, str]:
    return str(item.get("topic_id", "")), str(item.get("description", "")).strip()


def record_validation_discards(stats: MergeStats, validation_stats: ExtractionValidationStats) -> None:
    stats.discarded_extraction_items += (
        validation_stats.discarded_claims
        + validation_stats.discarded_evidence
        + validation_stats.discarded_missing
        + validation_stats.discarded_risks
        + validation_stats.discarded_contradictions
    )
