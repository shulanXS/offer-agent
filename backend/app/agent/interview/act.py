"""Interview Act 节点：根据合法决策生成自然话术。"""
from __future__ import annotations

import logging
from typing import Any

from app.agent.interview.prompts import ACT_PROMPT, ACT_SYSTEM_PROMPT
from app.agent.interview.transitions import build_topic_handoff_message
from app.core.config import settings
from app.llm.factory import create_llm_client, extract_spoken_message
from app.services.interview.actions import build_template_fallback_act_message


logger = logging.getLogger("uvicorn.error")


class InterviewActAgent:
    def generate_message(
        self,
        *,
        decision: dict[str, Any],
        topic: dict[str, Any],
        next_topic: dict[str, Any] | None,
        topic_messages: list[dict[str, Any]],
        latest_answer: str,
        interview_type: str,
        last_action: str = "",
        trace_id: str = "",
    ) -> str:
        action = str(decision.get("action", "")).strip()
        expected_information = decision.get("expected_information") or []
        target_signal = str(expected_information[0]).strip() if expected_information else ""
        if action == "next_topic" and next_topic is not None:
            return build_topic_handoff_message(
                completed_topic=topic,
                next_topic=next_topic,
                interview_type=interview_type,
                trace_id=trace_id,
            )
        if action == "finish":
            from app.agent.interview.transitions import build_completion_message

            return build_completion_message(topic_count=0)

        client = create_llm_client(settings.llm_provider, settings.llm_model)
        interview_label = "校招" if interview_type == "campus" else "社招"
        prompt = ACT_PROMPT.format(
            interview_label=interview_label,
            topic_name=topic.get("name", ""),
            objective=topic.get("objective", ""),
            action=action,
            reason=decision.get("reason", ""),
            expected_information=expected_information,
            target_signal=target_signal or "（未指定）",
            last_action=last_action or "（无）",
            conversation_history=_format_conversation_history(topic_messages),
            latest_answer=latest_answer,
            next_opening_question=(next_topic or {}).get("opening_question", ""),
        )
        try:
            payload = client.generate_json(
                prompt,
                ACT_SYSTEM_PROMPT,
                operation_name="interview_act",
                trace_id=trace_id,
            )
            message = extract_spoken_message(payload)
            if message:
                return message
        except Exception:
            logger.exception("[trace_id=%s] interview act failed, using template fallback", trace_id or "-")
        return build_template_fallback_act_message(
            action,
            topic,
            latest_answer=latest_answer,
            target_signal=target_signal,
            last_action=last_action,
            verify_contradiction=bool(decision.get("_verify_contradiction"))
            or str(target_signal).startswith("澄清："),
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
