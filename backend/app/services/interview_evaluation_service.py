"""V2 面试评估服务（06 小步 1）。"""
from __future__ import annotations

import logging
import time
from typing import Any

from app.core.errors import ErrorCode, raise_app_error
from app.core.events import commit_event
from app.core.logging_utils import log_payload, new_trace_id
from app.db.store import Store
from app.services.interview_evaluation.context import build_evaluation_context
from app.services.interview_evaluation.minimal_report import build_minimal_evaluation_report
from app.services.interview_evaluation.report import build_evidence_driven_report
from app.services.interview_agent_service import InterviewAgentService
from app.services.learning.record import record_session_outcome


logger = logging.getLogger("uvicorn.error")


class InterviewEvaluationService:
    def __init__(self) -> None:
        self.store = Store()
        self.live_service = InterviewAgentService()

    def evaluate_interview(self, user_id: int, session_id: str) -> dict[str, Any]:
        record = self._get_v2_record(user_id, session_id)
        trace_id = self._trace_id_from_record(record)

        if record["status"] == "completed" and record.get("evaluation"):
            return self._build_response(record)

        if record["status"] != "evaluating":
            raise_app_error(
                409,
                ErrorCode.SESSION_NOT_ACTIVE,
                "当前会话尚未进入评估状态",
                trace_id=trace_id,
            )

        started = time.perf_counter()
        evaluation = self._generate_report(record, trace_id=trace_id)
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        self.store.update_session(
            session_id,
            status="completed",
            evaluation=evaluation,
        )

        try:
            record_session_outcome(user_id=user_id, session_id=session_id)
        except Exception:
            logger.exception(
                "[trace_id=%s] record_session_outcome failed: session_id=%s",
                trace_id,
                session_id,
            )

        updated = self._get_v2_record(user_id, session_id)
        log_payload(
            logger,
            logging.INFO,
            f"Interview evaluation completed: session_id={session_id}",
            {
                "source": evaluation.get("source"),
                "coverage_rate": evaluation.get("coverage_rate"),
                "overall_confidence": evaluation.get("overall_confidence"),
                "evidence_topics": evaluation.get("coverage", {}).get("topics_with_evidence_count"),
                "risks_count": len(evaluation.get("risks") or []),
                "unverified_count": len(evaluation.get("unverified_items") or []),
                "elapsed_ms": elapsed_ms,
            },
            trace_id=trace_id,
        )
        commit_event(
            logger,
            "evaluation.completed",
            trace_id=trace_id,
            session_id=session_id,
            user_id=user_id,
            source=evaluation.get("source"),
            overall_score=evaluation.get("overall_score"),
            elapsed_ms=elapsed_ms,
        )
        return self._build_response(updated)

    def get_evaluation(self, user_id: int, session_id: str) -> dict[str, Any] | None:
        record = self.store.get_interview_session_record(user_id, session_id)
        if not record:
            return None
        evaluation = record.get("evaluation")
        if not evaluation:
            return None
        return {
            "session_id": session_id,
            "status": record["status"],
            "evaluation": evaluation,
        }

    def is_v2_evaluable_session(self, user_id: int, session_id: str) -> bool:
        record = self.store.get_interview_session_record(user_id, session_id)
        if not record:
            return False
        return record["status"] in {"evaluating", "completed"}

    def _generate_report(self, record: dict[str, Any], *, trace_id: str) -> dict[str, Any]:
        confirmed_plan_id = record.get("confirmed_plan_id")
        if not confirmed_plan_id:
            raise_app_error(409, ErrorCode.INTERVIEW_CONFIG_INVALID, "缺少已锁定计划", trace_id=trace_id)

        plan_record = self.store.get_plan_by_id(str(confirmed_plan_id))
        if not plan_record:
            raise_app_error(404, ErrorCode.SESSION_NOT_FOUND, "计划不存在", trace_id=trace_id)

        runtime_state = record.get("workflow_state") or {}
        evaluation_context = build_evaluation_context(
            plan_json=plan_record["plan_json"],
            configuration=record["configuration"],
            runtime_state=runtime_state,
            messages=record.get("messages") or [],
        )
        # v1.1: 报告语言跟随 interview_language
        report_language = str(record.get("configuration", {}).get("interview_language") or "en")
        try:
            return build_evidence_driven_report(
                plan_json=plan_record["plan_json"],
                configuration=record["configuration"],
                runtime_state=runtime_state,
                evaluation_context=evaluation_context,
                trace_id=trace_id,
                language=report_language,
            )
        except Exception as exc:
            logger.warning(
                "[trace_id=%s] evidence-driven evaluation failed, falling back to minimal report: %s",
                trace_id,
                exc,
            )
            try:
                minimal = build_minimal_evaluation_report(
                    plan_json=plan_record["plan_json"],
                    configuration=record["configuration"],
                    runtime_state=runtime_state,
                    evaluation_context=evaluation_context,
                    language=report_language,
                )
                # B1：降级报告 schema 显式标注
                if isinstance(minimal, dict):
                    minimal.setdefault("degraded", True)
                    minimal.setdefault("degraded_reason", "evidence_driven_failed")
                    minimal.setdefault(
                        "degraded_message",
                        "本场评估采用降级路径（极简模板），建议重新面试或联系管理员。",
                    )
                return minimal
            except Exception:
                logger.exception("[trace_id=%s] Interview evaluation failed: session_id=%s", trace_id, record["id"])
                raise_app_error(
                    500,
                    ErrorCode.INTERVIEW_EVALUATION_FAILED,
                    "评估生成失败，请稍后重试",
                    trace_id=trace_id,
                    details=str(exc),
                )

    def _get_v2_record(self, user_id: int, session_id: str) -> dict[str, Any]:
        if not self.live_service.is_v2_session(user_id, session_id):
            raise_app_error(404, ErrorCode.SESSION_NOT_FOUND, "面试会话不存在")
        record = self.store.get_interview_session_record(user_id, session_id)
        if not record:
            raise_app_error(404, ErrorCode.SESSION_NOT_FOUND, "面试会话不存在")
        return record

    @staticmethod
    def _build_response(record: dict[str, Any]) -> dict[str, Any]:
        evaluation = record.get("evaluation")
        if not evaluation:
            raise_app_error(500, ErrorCode.INTERVIEW_EVALUATION_FAILED, "评估结果不存在")
        return {
            "session_id": record["id"],
            "status": record["status"],
            "evaluation": evaluation,
        }

    @staticmethod
    def _trace_id_from_record(record: dict[str, Any]) -> str:
        workflow_state = record.get("workflow_state") or {}
        return str(workflow_state.get("trace_id") or new_trace_id("evaluation"))
