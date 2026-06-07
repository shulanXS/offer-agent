"""Evidence 提取结果校验（05 小步 2）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.interview.actions import PROBE_ACTIONS
from app.services.interview.memory.contradictions import sanitize_contradiction_description
from app.services.interview.memory.signal_map import find_plan_topic, resolve_plan_signal


ALLOWED_ANSWER_QUALITY = frozenset({"weak", "partial", "strong"})
ALLOWED_POLARITIES = frozenset({"positive", "negative", "neutral"})
ALLOWED_CLAIM_STATUS = frozenset({"unverified", "verified"})

EMPTY_EXTRACTION: dict[str, Any] = {
    "answer_quality": "partial",
    "claims": [],
    "evidence": [],
    "missing_information": [],
    "risks": [],
    "potential_contradictions": [],
}


@dataclass
class ExtractionValidationStats:
    discarded_claims: int = 0
    discarded_evidence: int = 0
    discarded_missing: int = 0
    discarded_risks: int = 0
    discarded_contradictions: int = 0


def empty_extraction(*, answer_quality: str = "partial") -> dict[str, Any]:
    quality = answer_quality if answer_quality in ALLOWED_ANSWER_QUALITY else "partial"
    return {**EMPTY_EXTRACTION, "answer_quality": quality}


def validate_extraction_result(
    raw: Any,
    *,
    plan_json: dict[str, Any],
    current_topic: dict[str, Any],
    latest_answer: str,
) -> tuple[dict[str, Any], ExtractionValidationStats]:
    stats = ExtractionValidationStats()
    if not isinstance(raw, dict):
        return empty_extraction(), stats

    current_topic_id = str(current_topic.get("id", ""))
    answer_quality = str(raw.get("answer_quality", "partial")).strip()
    if answer_quality not in ALLOWED_ANSWER_QUALITY:
        answer_quality = "partial"

    claims: list[dict[str, Any]] = []
    for item in raw.get("claims") or []:
        normalized = _normalize_claim(
            item,
            plan_json=plan_json,
            current_topic_id=current_topic_id,
            latest_answer=latest_answer,
        )
        if normalized:
            claims.append(normalized)
        else:
            stats.discarded_claims += 1

    evidence: list[dict[str, Any]] = []
    for item in raw.get("evidence") or []:
        normalized = _normalize_evidence(
            item,
            current_topic=current_topic,
            latest_answer=latest_answer,
        )
        if normalized:
            evidence.append(normalized)
        else:
            stats.discarded_evidence += 1

    missing_information: list[dict[str, Any]] = []
    for item in raw.get("missing_information") or []:
        normalized = _normalize_missing(item, current_topic=current_topic)
        if normalized:
            missing_information.append(normalized)
        else:
            stats.discarded_missing += 1

    risks: list[str] = []
    for item in raw.get("risks") or []:
        text = str(item).strip()
        if text and text not in risks:
            risks.append(text)
        elif item:
            stats.discarded_risks += 1

    contradictions: list[dict[str, Any]] = []
    for item in raw.get("potential_contradictions") or []:
        normalized = _normalize_contradiction(item, current_topic_id=current_topic_id, latest_answer=latest_answer)
        if normalized:
            contradictions.append(normalized)
        else:
            stats.discarded_contradictions += 1

    return {
        "answer_quality": answer_quality,
        "claims": claims,
        "evidence": evidence,
        "missing_information": missing_information,
        "risks": risks,
        "potential_contradictions": contradictions,
    }, stats


def quote_in_latest_answer(quote: str, latest_answer: str) -> bool:
    normalized_quote = _normalize_text(quote)
    normalized_answer = _normalize_text(latest_answer)
    if not normalized_quote or not normalized_answer:
        return False
    return normalized_quote in normalized_answer


def _normalize_claim(
    item: Any,
    *,
    plan_json: dict[str, Any],
    current_topic_id: str,
    latest_answer: str,
) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    topic_id = str(item.get("topic_id") or current_topic_id).strip()
    topic = find_plan_topic(plan_json, topic_id)
    if topic is None:
        return None
    content = str(item.get("content", "")).strip()
    if not content:
        return None
    if not _content_grounded_in_answer(content, latest_answer):
        return None
    status = str(item.get("status", "unverified")).strip()
    if status not in ALLOWED_CLAIM_STATUS:
        status = "unverified"
    probe_hint = str(item.get("probe_hint", "")).strip()
    if probe_hint and probe_hint not in PROBE_ACTIONS:
        probe_hint = ""
    normalized = {"topic_id": topic_id, "content": content, "status": status}
    if probe_hint:
        normalized["probe_hint"] = probe_hint
    return normalized


def _normalize_evidence(item: Any, *, current_topic: dict[str, Any], latest_answer: str) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    topic_id = str(item.get("topic_id") or current_topic.get("id", "")).strip()
    if topic_id != str(current_topic.get("id", "")):
        return None
    matched_signal = resolve_plan_signal(str(item.get("matched_signal", "")), current_topic)
    if not matched_signal:
        return None
    quote = str(item.get("quote", "")).strip()
    if not quote or not quote_in_latest_answer(quote, latest_answer):
        return None
    polarity = str(item.get("polarity", "neutral")).strip()
    if polarity not in ALLOWED_POLARITIES:
        polarity = "neutral"
    strength = _clamp_strength(item.get("strength"))
    rationale = str(item.get("rationale", "")).strip()
    return {
        "topic_id": topic_id,
        "matched_signal": matched_signal,
        "polarity": polarity,
        "quote": quote,
        "strength": strength,
        "rationale": rationale,
    }


def _normalize_missing(item: Any, *, current_topic: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    topic_id = str(item.get("topic_id") or current_topic.get("id", "")).strip()
    if topic_id != str(current_topic.get("id", "")):
        return None
    signal = resolve_plan_signal(str(item.get("signal", "")), current_topic)
    if not signal:
        return None
    return {"topic_id": topic_id, "signal": signal, "from_plan": True}


def _normalize_contradiction(item: Any, *, current_topic_id: str, latest_answer: str) -> dict[str, Any] | None:
    if isinstance(item, str):
        description = sanitize_contradiction_description(item.strip())
        if not description:
            return None
        return {
            "topic_id": current_topic_id,
            "description": description,
            "status": "unverified",
        }
    if not isinstance(item, dict):
        return None
    description = sanitize_contradiction_description(str(item.get("description") or item.get("content") or "").strip())
    if not description:
        return None
    related_quote = str(item.get("related_quote") or item.get("quote") or "").strip()
    if related_quote and not quote_in_latest_answer(related_quote, latest_answer):
        related_quote = ""
    topic_id = str(item.get("topic_id") or current_topic_id).strip()
    payload: dict[str, Any] = {
        "topic_id": topic_id,
        "description": description,
        "status": "unverified",
    }
    if related_quote:
        payload["related_quote"] = related_quote
    return payload


def _content_grounded_in_answer(content: str, latest_answer: str) -> bool:
    normalized_content = _normalize_text(content)
    normalized_answer = _normalize_text(latest_answer)
    if not normalized_content or not normalized_answer:
        return False
    if normalized_content in normalized_answer:
        return True
    if len(normalized_content) >= 6:
        fragment = normalized_content[: max(6, len(normalized_content) // 2)]
        return fragment in normalized_answer
    return False


def _clamp_strength(value: Any) -> float:
    try:
        strength = float(value)
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, min(1.0, strength))


def _normalize_text(text: str) -> str:
    return " ".join(str(text).split())
