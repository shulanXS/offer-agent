"""Decide 消费工作记忆的辅助函数（05 小步 3）。"""
from __future__ import annotations

from typing import Any

from app.services.interview.actions import build_rule_fallback_probe_action
from app.services.interview.memory.contradictions import pick_unverified_contradiction


STRONG_EVIDENCE_MIN_STRENGTH = 0.6


def format_missing_information(memory_context: dict[str, Any] | None) -> str:
    if not memory_context:
        return "（暂无）"
    items = memory_context.get("missing_information") or []
    if not items:
        return "（当前主题暂无缺口）"
    lines = [f"- {item.get('signal', '')}" for item in items if isinstance(item, dict) and item.get("signal")]
    return "\n".join(lines) or "（当前主题暂无缺口）"


def format_covered_signals(memory_context: dict[str, Any] | None) -> str:
    if not memory_context:
        return "（暂无）"
    covered = (memory_context.get("relevant_memory") or {}).get("covered_signals") or []
    if not covered:
        return "（暂无）"
    return "、".join(str(item) for item in covered)


def format_recent_evidence_summary(memory_context: dict[str, Any] | None, *, limit: int = 5) -> str:
    if not memory_context:
        return "（暂无）"
    recent = (memory_context.get("relevant_memory") or {}).get("recent_evidence") or []
    lines: list[str] = []
    for item in recent[:limit]:
        if not isinstance(item, dict):
            continue
        signal = str(item.get("matched_signal", "")).strip()
        quote = str(item.get("quote", "")).strip()
        strength = item.get("strength", "")
        if signal and quote:
            lines.append(f"- {signal}: 「{quote}」(strength={strength})")
    return "\n".join(lines) or "（暂无）"


def filter_probeable_gaps(
    memory_context: dict[str, Any] | None,
    *,
    last_probed_information: str = "",
) -> list[dict[str, Any]]:
    if not memory_context:
        return []
    last_probed = str(last_probed_information or "").strip()
    gaps: list[dict[str, Any]] = []
    for item in memory_context.get("missing_information") or []:
        if not isinstance(item, dict):
            continue
        signal = str(item.get("signal", "")).strip()
        if not signal:
            continue
        if last_probed and signal == last_probed:
            continue
        gaps.append(item)
    return gaps


def topic_is_sufficiently_covered(memory_context: dict[str, Any] | None) -> bool:
    if not memory_context:
        return False
    gaps = memory_context.get("missing_information") or []
    if gaps:
        return False
    relevant = memory_context.get("relevant_memory") or {}
    covered = relevant.get("covered_signals") or []
    if covered:
        return True
    for item in relevant.get("recent_evidence") or []:
        if not isinstance(item, dict):
            continue
        try:
            strength = float(item.get("strength", 0))
        except (TypeError, ValueError):
            strength = 0.0
        if strength >= STRONG_EVIDENCE_MIN_STRENGTH:
            return True
    return False


def probe_action_for_signal(signal: str, topic: dict[str, Any]) -> str:
    token = str(signal).strip()
    if any(keyword in token for keyword in ("指标", "结果", "数据", "性能")):
        return "probe_metric"
    if any(keyword in token for keyword in ("贡献", "职责", "负责", "所有权")):
        return "probe_ownership"
    if any(keyword in token for keyword in ("取舍", "方案", "权衡", "选型")):
        return "probe_tradeoff"
    if any(keyword in token for keyword in ("风险", "故障", "异常")):
        return "probe_risk"
    if any(keyword in token for keyword in ("细节", "实现", "技术")):
        return "probe_detail"
    return build_rule_fallback_probe_action(topic)


def pick_next_gap(
    memory_context: dict[str, Any] | None,
    *,
    last_probed_information: str = "",
) -> dict[str, Any] | None:
    gaps = filter_probeable_gaps(memory_context, last_probed_information=last_probed_information)
    return gaps[0] if gaps else None


def memory_has_actionable_coverage(memory_context: dict[str, Any] | None) -> bool:
    """已有 evidence / 覆盖信号时才用 gaps 驱动追问，避免首轮空 extract 阻断切题。"""
    if not memory_context:
        return False
    relevant = memory_context.get("relevant_memory") or {}
    if relevant.get("covered_signals") or relevant.get("recent_evidence"):
        return True
    return False


def build_contradiction_verification_decision(
    *,
    topic_id: str,
    contradiction: dict[str, Any],
) -> dict[str, Any]:
    description = str(contradiction.get("description", "")).strip() or "前后表述待核实"
    return {
        "action": "probe_detail",
        "target_topic_id": topic_id,
        "reason": "待核实前后表述是否一致",
        "expected_information": [f"澄清：{description[:60]}"],
        "should_change_topic": False,
        "_verify_contradiction": True,
    }


def should_attempt_contradiction_verification(
    *,
    runtime_state: dict[str, Any],
    memory_context: dict[str, Any] | None,
    current_topic_id: str,
) -> bool:
    if bool(runtime_state.get("contradiction_verification_used")):
        return False
    return pick_unverified_contradiction(memory_context, current_topic_id=current_topic_id) is not None


def format_contradictions(memory_context: dict[str, Any] | None) -> str:
    from app.services.interview.memory.contradictions import format_contradictions as _format

    return _format(memory_context)
