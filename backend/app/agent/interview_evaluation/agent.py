"""Evaluation Agent（06 小步 2）。"""
from __future__ import annotations

import logging
import time
from typing import Any

from app.agent.interview_evaluation.prompts import EVALUATION_SYSTEM_PROMPT, build_evaluation_prompt
from app.agent.interview_evaluation.validator import EvaluationAgentValidationError, validate_agent_narrative
from app.core.config import settings
from app.llm.factory import create_llm_client


logger = logging.getLogger("uvicorn.error")


class EvaluationAgent:
    def enrich_narrative(
        self,
        *,
        evaluation_context: dict[str, Any],
        competencies: list[dict[str, Any]],
        plan_json: dict[str, Any],
        trace_id: str = "",
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        started = time.perf_counter()
        prompt = build_evaluation_prompt(evaluation_context=evaluation_context, competencies=competencies)
        try:
            client = create_llm_client(settings.llm_provider, settings.llm_model)
            payload = client.generate_json(
                prompt,
                EVALUATION_SYSTEM_PROMPT,
                operation_name="interview_evaluation_enrich",
                trace_id=trace_id,
            )
            validated = validate_agent_narrative(payload, plan_json=plan_json)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            model_info = {
                "provider": settings.llm_provider,
                "model": settings.llm_model,
                "operation": "interview_evaluation_enrich",
                "elapsed_ms": elapsed_ms,
            }
            return validated, model_info
        except EvaluationAgentValidationError:
            logger.warning(
                "[trace_id=%s] evaluation agent validation failed",
                trace_id or "-",
            )
            return None, None
        except Exception:
            logger.exception(
                "[trace_id=%s] evaluation agent failed, using rule narrative",
                trace_id or "-",
            )
            return None, None
