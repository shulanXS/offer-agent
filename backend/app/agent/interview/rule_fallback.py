"""Interview Decide 规则降级：LLM 调用失败时使用确定性决策。"""
from __future__ import annotations

from typing import Any

from app.services.interview.actions import build_rule_fallback_probe_action
from app.services.interview.constants import MAX_TOPIC_PROBE_COUNT
from app.services.interview.memory.decide_support import (
    build_contradiction_verification_decision,
    memory_has_actionable_coverage,
    pick_next_gap,
    probe_action_for_signal,
    should_attempt_contradiction_verification,
    topic_is_sufficiently_covered,
)
from app.services.interview.memory.contradictions import pick_unverified_contradiction


VAGUE_ANSWER_MAX_LEN = 40


def build_rule_fallback_decision(
    *,
    topic: dict[str, Any],
    latest_answer: str,
    runtime_state: dict[str, Any],
    has_next_topic: bool,
    memory_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    topic_id = str(topic.get("id", ""))
    cleaned = latest_answer.strip()
    expected = [str(item) for item in (topic.get("expected_signals") or []) if str(item).strip()]
    probe_count = int(runtime_state.get("current_topic_probe_count") or 0)
    last_probed = str(runtime_state.get("last_probed_information") or "").strip()
    next_gap = pick_next_gap(memory_context, last_probed_information=last_probed)

    if (
        should_attempt_contradiction_verification(
            runtime_state=runtime_state,
            memory_context=memory_context,
            current_topic_id=topic_id,
        )
        and probe_count < MAX_TOPIC_PROBE_COUNT
    ):
        contradiction = pick_unverified_contradiction(memory_context, current_topic_id=topic_id)
        if contradiction is not None:
            return build_contradiction_verification_decision(topic_id=topic_id, contradiction=contradiction)

    if topic_is_sufficiently_covered(memory_context):
        if has_next_topic:
            return {
                "action": "next_topic",
                "target_topic_id": topic_id,
                "reason": "当前主题期望信号已基本覆盖，准备切换下一主题",
                "expected_information": [],
                "should_change_topic": True,
            }
        return {
            "action": "finish",
            "target_topic_id": topic_id,
            "reason": "所有主题已完成",
            "expected_information": [],
            "should_change_topic": True,
        }

    if memory_has_actionable_coverage(memory_context) and next_gap and probe_count < MAX_TOPIC_PROBE_COUNT:
        signal = str(next_gap.get("signal", "")).strip()
        action = probe_action_for_signal(signal, topic)
        return {
            "action": action,
            "target_topic_id": topic_id,
            "reason": f"仍需补充与主题相关的「{signal}」",
            "expected_information": [signal],
            "should_change_topic": False,
        }

    if len(cleaned) < VAGUE_ANSWER_MAX_LEN and probe_count < MAX_TOPIC_PROBE_COUNT:
        action = build_rule_fallback_probe_action(topic)
        fallback_expected = expected[:2] or ["具体实践", "个人贡献"]
        return {
            "action": action,
            "target_topic_id": topic_id,
            "reason": "回答较简略，仍需补充与主题相关的具体信息",
            "expected_information": fallback_expected,
            "should_change_topic": False,
        }

    if has_next_topic:
        return {
            "action": "next_topic",
            "target_topic_id": topic_id,
            "reason": "当前主题已获得足够信息，准备切换下一主题",
            "expected_information": [],
            "should_change_topic": True,
        }
    return {
        "action": "finish",
        "target_topic_id": topic_id,
        "reason": "所有主题已完成",
        "expected_information": [],
        "should_change_topic": True,
    }
