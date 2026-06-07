"""Interview Evidence Extractor（LLM + 校验）。"""
from __future__ import annotations

import logging
import time
from typing import Any

from app.agent.interview.evidence.prompts import EVIDENCE_PROMPT, EVIDENCE_SYSTEM_PROMPT
from app.core.config import settings
from app.llm.factory import create_llm_client
from app.services.interview.memory.extraction_schema import (
    ExtractionValidationStats,
    empty_extraction,
    validate_extraction_result,
)


logger = logging.getLogger("uvicorn.error")


class InterviewEvidenceExtractor:
    def extract(
        self,
        *,
        current_topic: dict[str, Any],
        plan_json: dict[str, Any],
        topic_messages: list[dict[str, Any]],
        topic_summaries: dict[str, Any],
        latest_answer: str,
        working_memory: dict[str, Any],
        trace_id: str = "",
    ) -> tuple[dict[str, Any], ExtractionValidationStats]:
        started = time.perf_counter()
        prompt = EVIDENCE_PROMPT.format(
            topic_id=current_topic.get("id", ""),
            topic_name=current_topic.get("name", ""),
            objective=current_topic.get("objective", ""),
            dimension=current_topic.get("dimension", ""),
            expected_signals=current_topic.get("expected_signals", []),
            focus_points=current_topic.get("focus_points", []),
            topic_summaries=_format_topic_summaries(topic_summaries),
            conversation_history=_format_conversation_history(topic_messages),
            latest_answer=latest_answer,
            existing_claim_count=len(working_memory.get("claims") or []),
            existing_evidence_count=len(working_memory.get("evidence") or []),
        )
        try:
            client = create_llm_client(settings.llm_provider, settings.llm_model)
            payload = client.generate_json(
                prompt,
                EVIDENCE_SYSTEM_PROMPT,
                operation_name="interview_evidence_extract",
                trace_id=trace_id,
            )
            validated, stats = validate_extraction_result(
                payload,
                plan_json=plan_json,
                current_topic=current_topic,
                latest_answer=latest_answer,
            )
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            logger.info(
                "[trace_id=%s] evidence extract ok claims=%d evidence=%d discarded=%d elapsed_ms=%d",
                trace_id or "-",
                len(validated.get("claims") or []),
                len(validated.get("evidence") or []),
                stats.discarded_claims
                + stats.discarded_evidence
                + stats.discarded_missing
                + stats.discarded_risks
                + stats.discarded_contradictions,
                elapsed_ms,
            )
            return validated, stats
        except Exception:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            logger.exception(
                "[trace_id=%s] evidence extract failed, returning empty increment elapsed_ms=%d",
                trace_id or "-",
                elapsed_ms,
            )
            return empty_extraction(), ExtractionValidationStats()


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
