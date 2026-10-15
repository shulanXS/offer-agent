"""证据驱动能力评分（06 小步 2，确定性推导）。"""
from __future__ import annotations

from typing import Any

from app.services.interview_evaluation.evidence_references import (
    build_competency_answer_rounds,
    build_evidence_references,
)
from app.services.interview.memory.merge import EVIDENCE_COVERAGE_MIN_STRENGTH
from app.services.interview.memory.signal_map import all_plan_topic_ids, find_plan_topic, plan_signals_for_topic

ALLOWED_COMPETENCY_STATUS = frozenset({"verified", "partially_verified", "unverified"})


def derive_competencies(
    *,
    plan_json: dict[str, Any],
    evaluation_context: dict[str, Any],
    runtime_state: dict[str, Any],
) -> list[dict[str, Any]]:
    evidence_by_topic = evaluation_context.get("evidence_by_topic") or {}
    messages_by_topic = evaluation_context.get("messages_by_topic") or {}
    completed_topic_ids = {str(item) for item in (runtime_state.get("completed_topic_ids") or [])}
    competencies: list[dict[str, Any]] = []

    for topic_id in all_plan_topic_ids(plan_json):
        topic = find_plan_topic(plan_json, topic_id)
        if not topic:
            continue
        bucket = evidence_by_topic.get(topic_id) or {}
        evidence = [item for item in (bucket.get("evidence") or []) if isinstance(item, dict)]
        covered = set(bucket.get("covered_signals") or [])
        expected = plan_signals_for_topic(topic)
        status = _derive_status(
            topic_id=topic_id,
            evidence=evidence,
            covered=covered,
            expected=expected,
            completed_topic_ids=completed_topic_ids,
        )
        score = _derive_score(status=status, evidence=evidence, covered=covered, expected=expected)
        confidence = _derive_confidence(
            status=status,
            evidence=evidence,
            covered_count=len(covered),
            expected_count=len(expected),
        )
        topic_messages = messages_by_topic.get(topic_id) or []
        evidence_references = build_evidence_references(evidence, topic_messages)
        answer_rounds = build_competency_answer_rounds(evidence, topic_messages)
        strengths, risks = _derive_topic_strengths_and_risks(
            topic=topic,
            evidence=evidence,
            evaluation_context=evaluation_context,
        )
        competencies.append(
            {
                "topic_id": topic_id,
                "name": str(topic.get("name") or topic_id),
                "dimension": str(topic.get("dimension") or ""),
                "status": status,
                "score": score,
                "confidence": confidence,
                "strengths": strengths,
                "risks": risks,
                "evidence_references": evidence_references,
                "answer_rounds": answer_rounds,
            }
        )
    return competencies


def _derive_status(
    *,
    topic_id: str,
    evidence: list[dict[str, Any]],
    covered: set[str],
    expected: list[str],
    completed_topic_ids: set[str],
) -> str:
    strong_evidence = _strong_evidence(evidence)
    if not strong_evidence and topic_id not in completed_topic_ids:
        return "unverified"
    if expected:
        if covered and all(signal in covered for signal in expected):
            return "verified"
        if covered or strong_evidence:
            return "partially_verified"
        return "unverified"
    if strong_evidence:
        return "verified" if len(strong_evidence) >= 2 else "partially_verified"
    return "unverified"


def _derive_score(
    *,
    status: str,
    evidence: list[dict[str, Any]],
    covered: set[str],
    expected: list[str],
) -> float | None:
    if status == "unverified":
        return None

    strengths = [float(item.get("strength", 0) or 0) for item in evidence]
    avg_strength = sum(strengths) / len(strengths) if strengths else 0.0
    coverage_ratio = len(covered) / len(expected) if expected else min(1.0, len(evidence) / 2)
    positive_items = [item for item in evidence if str(item.get("polarity", "")) == "positive"]
    negative_items = [item for item in evidence if str(item.get("polarity", "")) == "negative"]
    positive_count = len(positive_items)
    negative_count = len(negative_items)
    positive_strength = (
        sum(float(item.get("strength", 0) or 0) for item in positive_items) / len(positive_items)
        if positive_items
        else 0.0
    )

    if status == "verified":
        base = 3.4 + coverage_ratio * 1.0 + avg_strength * 0.6
        base -= negative_count * 0.35
    else:
        # partially_verified：「聊到了」不等于「表现尚可」，分数绑定正向证据与覆盖率
        if positive_count == 0:
            base = 1.0 + coverage_ratio * 0.35 + avg_strength * 0.12
        else:
            base = 1.6 + coverage_ratio * 1.15 + positive_strength * 0.55
        base -= negative_count * 0.75
        if negative_count > positive_count:
            base -= 0.45
        if negative_count >= 1 and positive_count == 0:
            base = min(base, 1.35)

    # 保留 0.5 步进的浮点（1.0–5.0），不再整数化。
    return round(max(1.0, min(5.0, base)), 2)


def _derive_confidence(
    *,
    status: str,
    evidence: list[dict[str, Any]],
    covered_count: int,
    expected_count: int,
) -> float:
    if status == "unverified":
        return round(min(0.4, 0.2 + len(evidence) * 0.05), 2)

    strengths = [float(item.get("strength", 0) or 0) for item in evidence]
    avg_strength = sum(strengths) / len(strengths) if strengths else 0.0
    coverage_ratio = covered_count / expected_count if expected_count else min(1.0, len(evidence) / 2)
    value = 0.35 + coverage_ratio * 0.35 + avg_strength * 0.25
    if status == "verified":
        value += 0.08
    return round(min(0.95, value), 2)


def _derive_topic_strengths_and_risks(
    *,
    topic: dict[str, Any],
    evidence: list[dict[str, Any]],
    evaluation_context: dict[str, Any],
) -> tuple[list[str], list[str]]:
    topic_id = str(topic.get("id", ""))
    strengths: list[str] = []
    risks: list[str] = []

    for item in evidence:
        quote = str(item.get("quote", "")).strip()
        if not quote:
            continue
        signal = str(item.get("matched_signal", "")).strip()
        polarity = str(item.get("polarity", "")).strip()
        label = f"{signal} — {quote}" if signal else quote
        if polarity == "positive" and label not in strengths:
            strengths.append(label)
        elif polarity == "negative" and label not in risks:
            risks.append(label)

    for item in evaluation_context.get("unverified_items") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("topic_id", "")).strip() != topic_id:
            continue
        content = str(item.get("content") or item.get("description") or "").strip()
        if content and content not in risks:
            risks.append(content)

    return strengths[:4], risks[:4]


def _strong_evidence(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    strong: list[dict[str, Any]] = []
    for item in evidence:
        try:
            strength = float(item.get("strength", 0) or 0)
        except (TypeError, ValueError):
            strength = 0.0
        if strength >= EVIDENCE_COVERAGE_MIN_STRENGTH and str(item.get("quote", "")).strip():
            strong.append(item)
    return strong
