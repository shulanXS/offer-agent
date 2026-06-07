"""潜在矛盾检测（05 小步 4：待验证，不定罪）。"""
from __future__ import annotations

from typing import Any

FORBIDDEN_CONCLUSION_WORDS = ("撒谎", "说谎", "造假", "欺骗", "虚假陈述")


def sanitize_contradiction_description(text: str) -> str:
    cleaned = str(text or "").strip()
    for word in FORBIDDEN_CONCLUSION_WORDS:
        cleaned = cleaned.replace(word, "待核实")
    if not cleaned:
        return "前后表述待核实"
    if not cleaned.startswith(("前后", "待核实", "需核实", "存在潜在")):
        return f"前后表述待核实：{cleaned}"
    return cleaned


def detect_potential_contradictions(
    *,
    existing_memory: dict[str, Any],
    new_claims: list[dict[str, Any]],
    new_evidence: list[dict[str, Any]],
    current_topic_id: str,
) -> list[dict[str, Any]]:
    """轻量确定性检测：新 claims/evidence 与历史 memory 比较。"""
    findings: list[dict[str, Any]] = []
    existing_claims = [item for item in (existing_memory.get("claims") or []) if isinstance(item, dict)]
    existing_evidence = [item for item in (existing_memory.get("evidence") or []) if isinstance(item, dict)]

    for new_item in new_claims:
        if not isinstance(new_item, dict):
            continue
        topic_id = str(new_item.get("topic_id") or current_topic_id)
        content = str(new_item.get("content", "")).strip()
        if not content:
            continue
        for old_claim in existing_claims:
            if str(old_claim.get("topic_id", "")) != topic_id:
                continue
            old_content = str(old_claim.get("content", "")).strip()
            if _has_opposing_claim(content, old_content):
                findings.append(
                    _make_contradiction(
                        topic_id=topic_id,
                        description=sanitize_contradiction_description(
                            f"新表述「{content}」与先前声明「{old_content}」可能存在不一致"
                        ),
                        related_quote=content,
                        related_claim=old_content,
                    )
                )

    for new_item in new_evidence:
        if not isinstance(new_item, dict):
            continue
        topic_id = str(new_item.get("topic_id") or current_topic_id)
        signal = str(new_item.get("matched_signal", "")).strip()
        polarity = str(new_item.get("polarity", "")).strip()
        quote = str(new_item.get("quote", "")).strip()
        if not signal or not quote:
            continue
        for old_item in existing_evidence + [item for item in new_evidence if item is not new_item]:
            if not isinstance(old_item, dict):
                continue
            if str(old_item.get("topic_id", "")) != topic_id:
                continue
            if str(old_item.get("matched_signal", "")).strip() != signal:
                continue
            old_polarity = str(old_item.get("polarity", "")).strip()
            old_quote = str(old_item.get("quote", "")).strip()
            if _is_polarity_conflict(polarity, old_polarity) or _has_opposing_claim(quote, old_quote):
                findings.append(
                    _make_contradiction(
                        topic_id=topic_id,
                        description=sanitize_contradiction_description(
                            f"关于「{signal}」，本轮「{quote}」与先前「{old_quote}」可能需要核实"
                        ),
                        related_quote=quote,
                        prior_quote=old_quote,
                        matched_signal=signal,
                    )
                )

    return _dedupe_contradictions(findings)


def pick_unverified_contradiction(
    memory_context: dict[str, Any] | None,
    *,
    current_topic_id: str = "",
) -> dict[str, Any] | None:
    if not memory_context:
        return None
    for item in memory_context.get("contradictions") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("status", "unverified")) != "unverified":
            continue
        if current_topic_id and str(item.get("topic_id", "")) != str(current_topic_id):
            continue
        return item
    return None


def format_contradictions(memory_context: dict[str, Any] | None) -> str:
    if not memory_context:
        return "（暂无）"
    lines: list[str] = []
    for item in memory_context.get("contradictions") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("status", "unverified")) != "unverified":
            continue
        description = str(item.get("description", "")).strip()
        if description:
            lines.append(f"- {description}")
    return "\n".join(lines) or "（暂无待核实矛盾）"


def _make_contradiction(**fields: Any) -> dict[str, Any]:
    return {
        "topic_id": str(fields.get("topic_id", "")),
        "description": sanitize_contradiction_description(str(fields.get("description", ""))),
        "status": "unverified",
        **{key: value for key, value in fields.items() if key not in {"topic_id", "description"}},
    }


def _dedupe_contradictions(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        key = (str(item.get("topic_id", "")), str(item.get("description", "")).strip())
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def _is_polarity_conflict(left: str, right: str) -> bool:
    if not left or not right or left == right:
        return False
    positive = {"positive"}
    negative = {"negative"}
    return (left in positive and right in negative) or (left in negative and right in positive)


def _has_opposing_claim(left: str, right: str) -> bool:
    if not left or not right or left == right:
        return False
    opposing_pairs = (
        ("独立", "协作"),
        ("独立", "团队"),
        ("负责", "未参与"),
        ("负责", "没有参与"),
        ("提升", "下降"),
        ("增加", "减少"),
        ("优化", "恶化"),
    )
    for a, b in opposing_pairs:
        if (a in left and b in right) or (b in left and a in right):
            return True
    return False
