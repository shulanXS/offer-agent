"""Interview Decide 节点：结构化决策，与 Act 分离。"""
from __future__ import annotations

import logging
from typing import Any

from app.agent.interview.prompts import get_decide_prompts
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
        interview_language: str = "en",
    ) -> dict[str, Any]:
        client = create_llm_client(settings.llm_provider, settings.llm_model)
        system_prompt, user_prompt = get_decide_prompts(interview_language)
        prompt = user_prompt.format(
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
            topic_summaries=_format_topic_summaries(topic_summaries, interview_language),
            conversation_history=_format_conversation_history(topic_messages, interview_language),
            latest_answer=latest_answer,
        )
        try:
            payload = client.generate_json(
                prompt,
                system_prompt,
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


def _format_conversation_history(messages: list[dict[str, Any]], language: str = "en") -> str:
    is_zh = language == "zh"
    interviewer_label = "面试官" if is_zh else "Interviewer"
    candidate_label = "候选人" if is_zh else "Candidate"
    empty_text = "（暂无对话）" if is_zh else "(no conversation yet)"
    lines: list[str] = []
    for message in messages:
        role = message.get("role")
        content = str(message.get("content", "")).strip()
        if not content:
            continue
        if role == "assistant":
            lines.append(f"{interviewer_label}: {content}")
        elif role == "user":
            lines.append(f"{candidate_label}: {content}")
    return "\n".join(lines) or empty_text


def _format_topic_summaries(topic_summaries: dict[str, Any], language: str = "en") -> str:
    if not topic_summaries:
        return "（尚无已完成主题）" if language == "zh" else "(no completed topic yet)"
    return "\n".join(f"- {key}: {value}" for key, value in topic_summaries.items())
