"""JD 要点验证（06 小步 3）：仅评估本场计划对齐的 JD 考察方向。"""
from __future__ import annotations

import re
from typing import Any

from app.services.interview.memory.signal_map import find_plan_topic

_SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$", re.IGNORECASE)


def build_jd_match(
    *,
    configuration: dict[str, Any],
    plan_json: dict[str, Any],
    evaluation_context: dict[str, Any],
    competencies: list[dict[str, Any]],
) -> dict[str, Any] | None:
    jd_text = str(configuration.get("jd_text", "") or "").strip()
    if not jd_text:
        return None

    alignments = extract_plan_jd_alignments(plan_json)
    competency_by_topic = {str(item.get("topic_id", "")): item for item in competencies}
    evidence_by_topic = evaluation_context.get("evidence_by_topic") or {}

    verified_aligned: list[dict[str, Any]] = []
    verified_with_risk: list[dict[str, Any]] = []
    unverified: list[dict[str, Any]] = []

    for item in alignments:
        topic_id = str(item.get("topic_id", "")).strip()
        requirement = str(item.get("display_requirement", "")).strip()
        if not topic_id or not requirement:
            continue
        status, quotes, note = _classify_alignment(
            topic_id=topic_id,
            competency=competency_by_topic.get(topic_id),
            evidence_by_topic=evidence_by_topic,
        )
        topic = find_plan_topic(plan_json, topic_id)
        entry: dict[str, Any] = {
            "requirement": requirement,
            "topic_id": topic_id,
            "topic_name": str((topic or {}).get("name") or "") or None,
            "evidence_quotes": quotes,
        }
        if note:
            entry["note"] = note
        if status == "verified_aligned":
            verified_aligned.append(entry)
        elif status == "verified_with_risk":
            verified_with_risk.append(entry)
        else:
            unverified.append(entry)

    in_scope_count = len(verified_aligned) + len(verified_with_risk) + len(unverified)
    return {
        "has_jd": True,
        "requirement_count": in_scope_count,
        "verified_aligned": verified_aligned,
        "verified_with_risk": verified_with_risk,
        "unverified": unverified,
        "summary": _build_jd_match_summary(
            in_scope_count=in_scope_count,
            verified_aligned_count=len(verified_aligned),
            verified_with_risk_count=len(verified_with_risk),
            unverified_count=len(unverified),
        ),
    }


def extract_plan_jd_alignments(plan_json: dict[str, Any]) -> list[dict[str, Any]]:
    """从已锁定计划中抽取本场对齐 JD 的考察方向（每个 topic 至多一条）。"""
    alignments: list[dict[str, Any]] = []
    seen_topic_ids: set[str] = set()

    for topic in plan_json.get("topics") or []:
        if not isinstance(topic, dict):
            continue
        topic_id = str(topic.get("id", "")).strip()
        if not topic_id or topic_id in seen_topic_ids:
            continue

        jd_refs = _collect_jd_refs(topic)
        if not jd_refs:
            continue

        seen_topic_ids.add(topic_id)
        alignments.append(
            {
                "topic_id": topic_id,
                "jd_refs": jd_refs,
                "display_requirement": _resolve_display_requirement(topic, jd_refs),
            }
        )
    return alignments


def extract_jd_requirements(jd_text: str, plan_json: dict[str, Any]) -> list[dict[str, Any]]:
    """兼容旧测试入口：仅返回计划内 jd: 对齐项。"""
    del jd_text
    return [
        {
            "requirement": item["display_requirement"],
            "source": "plan_topic",
            "topic_id": item["topic_id"],
        }
        for item in extract_plan_jd_alignments(plan_json)
    ]


def _collect_jd_refs(topic: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for ref in topic.get("source_refs") or []:
        ref_str = str(ref).strip()
        lowered = ref_str.lower()
        if not (lowered.startswith("jd:") or lowered.startswith("jd：")):
            continue
        text = ref_str.split(":", 1)[-1].split("：", 1)[-1].strip()
        if text and text not in refs:
            refs.append(text)
    return refs


def _resolve_display_requirement(topic: dict[str, Any], jd_refs: list[str]) -> str:
    human_refs = [ref for ref in jd_refs if not _looks_like_slug(ref)]
    if human_refs:
        return human_refs[0]

    name = str(topic.get("name", "")).strip()
    if name:
        return name

    objective = str(topic.get("objective", "")).strip()
    if objective:
        return objective[:80]

    return jd_refs[0]


def _looks_like_slug(text: str) -> bool:
    cleaned = text.strip()
    if len(cleaned) < 3:
        return False
    if re.search(r"[\u4e00-\u9fff]", cleaned):
        return False
    return bool(_SLUG_PATTERN.match(cleaned))


def _classify_alignment(
    *,
    topic_id: str,
    competency: dict[str, Any] | None,
    evidence_by_topic: dict[str, Any],
) -> tuple[str, list[str], str | None]:
    bucket = evidence_by_topic.get(topic_id) or {}
    evidence = [item for item in (bucket.get("evidence") or []) if isinstance(item, dict)]
    positive_quotes = [
        str(item.get("quote", "")).strip()
        for item in evidence
        if str(item.get("polarity", "")) == "positive" and str(item.get("quote", "")).strip()
    ]
    has_negative = any(str(item.get("polarity", "")) == "negative" for item in evidence)

    if not competency or str(competency.get("status", "")) == "unverified":
        if evidence:
            return "unverified", positive_quotes[:2], "已讨论该主题，但尚未形成充分验证结论。"
        return "unverified", [], "本场未充分讨论该主题。"

    status = str(competency.get("status", ""))
    risks = [str(item).strip() for item in (competency.get("risks") or []) if str(item).strip()]

    if status == "verified" and not risks and not has_negative:
        return "verified_aligned", positive_quotes[:2], None

    if status == "partially_verified" or risks or has_negative:
        note = risks[0] if risks else "回答存在缺口或薄弱点。"
        return "verified_with_risk", positive_quotes[:2], note

    return "verified_aligned", positive_quotes[:2], None


def _build_jd_match_summary(
    *,
    in_scope_count: int,
    verified_aligned_count: int,
    verified_with_risk_count: int,
    unverified_count: int,
) -> str:
    if in_scope_count == 0:
        return "本场计划未标注与 JD 对应的考察方向，请结合上方「考察覆盖」与各维度评价查看验证情况。"

    parts = [f"本场对齐 {in_scope_count} 条 JD 要点"]
    detail: list[str] = []
    if verified_aligned_count:
        detail.append(f"{verified_aligned_count} 条已验证")
    if verified_with_risk_count:
        detail.append(f"{verified_with_risk_count} 条有风险")
    if unverified_count:
        detail.append(f"{unverified_count} 条尚未验证")
    if detail:
        parts.append("：")
        parts.append("，".join(detail))
        parts.append("。")
    else:
        parts.append("。")
    return "".join(parts)
