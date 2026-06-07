"""Interview Agent 允许动作与决策校验。"""
from __future__ import annotations

from typing import Any

ALLOWED_ACTIONS = frozenset(
    {
        "probe_detail",
        "probe_ownership",
        "probe_metric",
        "probe_tradeoff",
        "probe_risk",
        "increase_difficulty",
        "decrease_difficulty",
        "next_topic",
        "finish",
    }
)

PROBE_ACTIONS = frozenset(
    {
        "probe_detail",
        "probe_ownership",
        "probe_metric",
        "probe_tradeoff",
        "probe_risk",
        "increase_difficulty",
        "decrease_difficulty",
    }
)

DEFAULT_PROBE_ACTION = "probe_detail"
FALLBACK_NEXT_ACTION = "next_topic"


def normalize_decision(raw: dict[str, Any], *, current_topic_id: str, has_next_topic: bool) -> dict[str, Any]:
    action = str(raw.get("action", "")).strip()
    if action not in ALLOWED_ACTIONS:
        action = DEFAULT_PROBE_ACTION if _looks_like_probe_request(raw) else FALLBACK_NEXT_ACTION

    target_topic_id = str(raw.get("target_topic_id") or current_topic_id).strip() or current_topic_id
    if target_topic_id != current_topic_id:
        target_topic_id = current_topic_id

    reason = str(raw.get("reason", "")).strip() or "继续当前主题考察"
    expected_information = raw.get("expected_information")
    if not isinstance(expected_information, list):
        expected_information = []
    expected_information = [str(item).strip() for item in expected_information if str(item).strip()][:5]

    should_change_topic = bool(raw.get("should_change_topic"))
    if action in {"next_topic", "finish"}:
        should_change_topic = True
    elif action in PROBE_ACTIONS:
        should_change_topic = False

    if action == "finish" and has_next_topic:
        action = FALLBACK_NEXT_ACTION

    if action == FALLBACK_NEXT_ACTION and not has_next_topic:
        action = "finish"

    return {
        "action": action,
        "target_topic_id": target_topic_id,
        "reason": reason,
        "expected_information": expected_information,
        "should_change_topic": should_change_topic,
    }


def build_rule_fallback_probe_action(topic: dict[str, Any]) -> str:
    dimension = str(topic.get("dimension", ""))
    if "项目" in dimension or "所有权" in dimension:
        return "probe_ownership"
    if "系统设计" in dimension or "取舍" in dimension:
        return "probe_tradeoff"
    if "指标" in dimension or "结果" in dimension:
        return "probe_metric"
    return DEFAULT_PROBE_ACTION


def build_template_fallback_act_message(
    action: str,
    topic: dict[str, Any],
    *,
    latest_answer: str = "",
    target_signal: str = "",
    last_action: str = "",
    verify_contradiction: bool = False,
) -> str:
    _ = last_action
    bridge = _build_bridge(latest_answer)
    signal = str(target_signal or "").strip()
    if verify_contradiction or signal.startswith("澄清："):
        clarification = signal.removeprefix("澄清：").strip() or "前后表述"
        question = f"想确认一下：{clarification}，这两处说法应该怎么理解？"
        if bridge and bridge != "好的，":
            if bridge.endswith(("。", "！", "？")):
                return f"{bridge}{question}"
            return f"{bridge}{question}"
        return question
    question = _probe_question_for_action(action, topic=topic, target_signal=signal)
    if bridge and question:
        if bridge.endswith(("。", "！", "？")):
            return f"{bridge}{question}"
        return f"{bridge}{question}"
    if question:
        return question
    name = str(topic.get("name", "")).strip() or "这个方向"
    return f"关于{name}，能再补充一些更具体的实践细节吗？"


def _build_bridge(latest_answer: str) -> str:
    from app.services.interview.act_support import build_answer_bridge

    snippet = build_answer_bridge(latest_answer).strip()
    if not snippet:
        return "好的，"
    if snippet.endswith(("。", "！", "？")):
        return snippet
    return f"{snippet}，"


def _probe_question_for_action(action: str, *, topic: dict[str, Any], target_signal: str) -> str:
    strategies = topic.get("probe_strategies") or []
    strategy_hint = str(strategies[0]).strip() if strategies else ""
    signal_prefix = f"关于{target_signal}，" if target_signal else ""
    templates = {
        "probe_ownership": f"{signal_prefix}你个人具体负责了哪些工作？结果是如何衡量的？",
        "probe_metric": f"想再补一下：{signal_prefix}具体用了哪些指标来验证？数据是怎么来的？",
        "probe_tradeoff": f"{signal_prefix}当时还考虑过哪些方案？最终选择这个方案的主要约束是什么？",
        "probe_risk": f"{signal_prefix}这个方案主要的风险点是什么？如果出现问题你会怎么处理？",
        "probe_detail": f"{signal_prefix}能再具体讲讲关键实现细节吗？你亲自做了哪些部分？",
        "increase_difficulty": "如果从更高并发或更复杂场景来看，你的方案还需要调整哪些地方？",
        "decrease_difficulty": "我们先从基础一点的说，这个场景里最关键的问题是什么？",
    }
    if action in templates:
        return templates[action]
    if strategy_hint:
        return f"我想再深入一点：{strategy_hint}"
    return ""


def _looks_like_probe_request(raw: dict[str, Any]) -> bool:
    if raw.get("should_change_topic") is False:
        return True
    action = str(raw.get("action", "")).strip()
    return action.startswith("probe_") or action.startswith("increase_") or action.startswith("decrease_")
