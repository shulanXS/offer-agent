"""Planning Agent：调用 LLM 生成面试计划，负责重试、降级与生成过程观测。"""
from __future__ import annotations

import logging
from collections import Counter
from threading import Lock
from typing import Any

from app.agent.interview_planning.prompts import build_planning_prompt
from app.agent.interview_planning.templates import build_template_fallback_plan
from app.agent.interview_planning.validator import PlanValidationError, validate_and_normalize_plan
from app.core.config import settings
from app.core.logging_utils import log_payload
from app.llm.factory import create_llm_client
from app.services.interview_planning.regeneration import validate_regeneration_strategy_outcome


logger = logging.getLogger("uvicorn.error")

MAX_PLANNING_ATTEMPTS = 3

_telemetry_lock = Lock()
_validation_failure_categories: Counter[str] = Counter()
_planning_outcomes: Counter[str] = Counter()


def record_validation_failure(reason: str, *, trace_id: str = "") -> None:
    category = categorize_validation_failure(reason)
    with _telemetry_lock:
        _validation_failure_categories[category] += 1
    logger.warning(
        "[trace_id=%s] planning_validation_failure category=%s reason=%s",
        trace_id or "-",
        category,
        reason[:240],
    )


def record_planning_outcome(*, source: str, degraded: bool, attempts: int, trace_id: str = "") -> None:
    outcome_key = f"source={source}|degraded={degraded}|attempts={attempts}"
    with _telemetry_lock:
        _planning_outcomes[outcome_key] += 1
    logger.info(
        "[trace_id=%s] planning_outcome source=%s degraded=%s generation_attempts=%s",
        trace_id or "-",
        source,
        degraded,
        attempts,
    )


def categorize_validation_failure(reason: str) -> str:
    text = reason.strip()
    if "主题数量" in text:
        return "topic_count"
    if "至少需要 4 个必考" in text:
        return "required_topics"
    if "estimated_minutes" in text or "时长总和" in text:
        return "duration_budget"
    if "必须维度未覆盖" in text:
        return "dimension_coverage"
    if "不得泄露" in text:
        return "summary_leak"
    if "缺少字段" in text or "必须是" in text:
        return "schema_shape"
    if "重新生成策略" in text or "adjust_topics" in text or "align_jd" in text or "align_resume" in text:
        return "regeneration_strategy"
    if "different_plan" in text or "有效差异" in text or "实质差异" in text:
        return "regeneration_diff"
    if "解析失败" in text:
        return "json_parse"
    return "other"


def snapshot() -> dict[str, dict[str, int]]:
    with _telemetry_lock:
        return {
            "validation_failures": dict(_validation_failure_categories),
            "outcomes": dict(_planning_outcomes),
        }


def reset_snapshot_for_tests() -> None:
    with _telemetry_lock:
        _validation_failure_categories.clear()
        _planning_outcomes.clear()


class PlanningAgent:
    def generate_plan(
        self,
        *,
        configuration: dict[str, Any],
        resume: dict[str, Any],
        role_knowledge_context: str = "",
        trace_id: str = "",
        previous_plan_summary: dict[str, Any] | None = None,
        regeneration_feedback: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        client = create_llm_client(settings.llm_provider, settings.llm_model)

        validation_feedback = ""
        last_error = "unknown"
        for attempt in range(1, MAX_PLANNING_ATTEMPTS + 1):
            prompt, system_prompt = build_planning_prompt(
                configuration=configuration,
                resume=resume,
                role_knowledge_context=role_knowledge_context,
                validation_feedback=validation_feedback,
                previous_plan_summary=previous_plan_summary,
                regeneration_feedback=regeneration_feedback,
            )
            try:
                payload = client.generate_json(
                    prompt,
                    system_prompt,
                    operation_name="planning_generate",
                    trace_id=trace_id,
                )
                validated = validate_and_normalize_plan(payload, configuration=configuration)
                if regeneration_feedback:
                    validate_regeneration_strategy_outcome(
                        plan=validated.plan,
                        candidate_summary=validated.candidate_summary,
                        configuration=configuration,
                        resume=resume,
                        regeneration_feedback=regeneration_feedback,
                        previous_plan_summary=previous_plan_summary,
                    )
                plan = {
                    **validated.plan,
                    "candidate_summary": validated.candidate_summary,
                    "source": "llm",
                    "generation_attempts": attempt,
                    "degraded": False,
                }
                logger.info(
                    "[trace_id=%s] Planning generated with LLM: attempt=%s topics=%s",
                    trace_id or "-",
                    attempt,
                    len(plan.get("topics", [])),
                )
                log_payload(logger, logging.INFO, "Planning LLM result", _safe_plan_log(plan), trace_id=trace_id)
                record_planning_outcome(
                    source="llm",
                    degraded=False,
                    attempts=attempt,
                    trace_id=trace_id,
                )
                return plan
            except PlanValidationError as exc:
                last_error = str(exc)
                validation_feedback = last_error
                record_validation_failure(last_error, trace_id=trace_id)
                logger.warning(
                    "[trace_id=%s] Planning validation failed: attempt=%s error=%s",
                    trace_id or "-",
                    attempt,
                    last_error,
                )
            except Exception as exc:
                last_error = str(exc)
                validation_feedback = f"模型输出解析失败: {last_error}"
                logger.warning(
                    "[trace_id=%s] Planning generation failed: attempt=%s error=%s",
                    trace_id or "-",
                    attempt,
                    last_error,
                )

        plan = build_template_fallback_plan(
            configuration=configuration,
            resume=resume,
            role_knowledge_context=role_knowledge_context,
            regeneration_feedback=regeneration_feedback,
        )
        plan.update(
            {
                "source": "template_fallback",
                "generation_attempts": MAX_PLANNING_ATTEMPTS,
                "degraded": True,
                "degraded_reason": last_error,
            }
        )
        logger.warning(
            "[trace_id=%s] Planning degraded to template fallback after %s attempts: reason=%s",
            trace_id or "-",
            MAX_PLANNING_ATTEMPTS,
            last_error,
        )
        record_planning_outcome(
            source="template_fallback",
            degraded=True,
            attempts=MAX_PLANNING_ATTEMPTS,
            trace_id=trace_id,
        )
        return plan


def _safe_plan_log(plan: dict[str, Any]) -> dict[str, Any]:
    topics = []
    for topic in plan.get("topics", []):
        if not isinstance(topic, dict):
            continue
        topics.append(
            {
                "id": topic.get("id"),
                "name": topic.get("name"),
                "dimension": topic.get("dimension"),
                "required": topic.get("required"),
                "estimated_minutes": topic.get("estimated_minutes"),
            }
        )
    return {
        "source": plan.get("source"),
        "generation_attempts": plan.get("generation_attempts"),
        "degraded": plan.get("degraded"),
        "topics": topics,
        "candidate_summary": plan.get("candidate_summary"),
    }
