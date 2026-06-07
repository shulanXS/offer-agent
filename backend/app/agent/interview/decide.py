"""Interview Decide 节点：结构化决策，与 Act 分离。"""
from __future__ import annotations

import logging
from typing import Any

from app.agent.interview.prompts import DECIDE_PROMPT, DECIDE_SYSTEM_PROMPT
from app.agent.interview.rule_fallback import build_rule_fallback_decision
from app.core.config import settings
from app.llm.factory import create_llm_client
from app.services.interview.memory.decide_support import (
    format_contradictions,
    format_covered_signals,
    format_missing_information,
    format_recent_evidence_summary,
)


logger = logging.getLogger("uvicorn.error")


class InterviewDecideAgent:
    def decide(
        self,
        *,
        topic: dict[str, Any],
        topic_messages: list[dict[str, Any]],
        topic_summaries: dict[str, Any],
        latest_answer: str,
        runtime_state: dict[str, Any],
        has_next_topic: bool,
        memory_context: dict[str, Any] | None = None,
        trace_id: str = "",
    ) -> dict[str, Any]:
        client = create_llm_client(settings.llm_provider, settings.llm_model)
        prompt = DECIDE_PROMPT.format(
            topic_id=topic.get("id", ""),
            topic_name=topic.get("name", ""),
            objective=topic.get("objective", ""),
            dimension=topic.get("dimension", ""),
            focus_points=topic.get("focus_points", []),
            expected_signals=topic.get("expected_signals", []),
            probe_strategies=topic.get("probe_strategies", []),
            covered_signals=format_covered_signals(memory_context),
            missing_information=format_missing_information(memory_context),
            recent_evidence_summary=format_recent_evidence_summary(memory_context),
            pending_contradictions=format_contradictions(memory_context),
            topic_summaries=_format_topic_summaries(topic_summaries),
            conversation_history=_format_conversation_history(topic_messages),
            latest_answer=latest_answer,
        )
        try:
            payload = client.generate_json(
                prompt,
                DECIDE_SYSTEM_PROMPT,
                operation_name="interview_decide",
                trace_id=trace_id,
            )
            if isinstance(payload, dict) and payload.get("action"):
                return payload
        except Exception:
            logger.exception("[trace_id=%s] interview decide failed, using rule fallback", trace_id or "-")
        return build_rule_fallback_decision(
            topic=topic,
            latest_answer=latest_answer,
            runtime_state=runtime_state,
            has_next_topic=has_next_topic,
            memory_context=memory_context,
        )


def _format_conversation_history(messages: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for message in messages:
        role = message.get("role")
        content = str(message.get("content", "")).strip()
        if not content:
            continue
        if role == "assistant":
            lines.append(f"面试官: {content}")
        elif role == "user":
            lines.append(f"候选人: {content}")
    return "\n".join(lines) or "（暂无对话）"


def _format_topic_summaries(topic_summaries: dict[str, Any]) -> str:
    if not topic_summaries:
        return "（尚无已完成主题）"
    return "\n".join(f"- {key}: {value}" for key, value in topic_summaries.items())
