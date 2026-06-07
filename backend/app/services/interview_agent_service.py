"""动态面试编排服务。"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from app.agent.interview.opening import render_opening_question
from app.agent.interview.transitions import build_early_finish_message
from app.core.constants import InterviewPlanSessionStatus
from app.core.errors import ErrorCode, raise_app_error
from app.core.logging_utils import log_payload, new_trace_id
from app.core.config import settings
from app.core.streaming import format_sse, stream_text
from app.db.store import Store
from app.services.interview.reply_handler import InterviewReplyHandler
from app.services.interview.boundaries import freeze_remaining_seconds
from app.services.interview.runtime_state import (
    build_initial_runtime_state,
    ensure_interview_clock_started,
    find_topic,
)
from app.services.interview.serialization import serialize_live_session_detail


logger = logging.getLogger("uvicorn.error")


class InterviewAgentService:
    def __init__(self) -> None:
        self.store = Store()
        self.reply_handler = InterviewReplyHandler()

    def is_v2_session(self, user_id: int, session_id: str) -> bool:
        record = self.store.get_interview_session_record(user_id, session_id)
        return record is not None

    def get_live_session_detail(self, user_id: int, session_id: str) -> dict[str, Any] | None:
        record = self._get_session_record(user_id, session_id)
        if record["status"] not in {"active", "evaluating", "completed"}:
            return None
        record = self._reconcile_reply_lock(record)
        return self._serialize_live(record, start_clock=True)

    def activate_interview(self, user_id: int, session_id: str) -> dict[str, Any]:
        record = self._get_session_record(user_id, session_id)
        trace_id = new_trace_id("interview")

        if record["status"] == "evaluating":
            raise_app_error(409, ErrorCode.SESSION_ALREADY_COMPLETED, "当前会话已结束", trace_id=trace_id)
        if record["status"] == "completed":
            raise_app_error(409, ErrorCode.SESSION_ALREADY_COMPLETED, "当前会话已结束", trace_id=trace_id)

        existing_live = self._return_if_already_activated(user_id, session_id, record, trace_id=trace_id)
        if existing_live:
            return existing_live

        if record["status"] != InterviewPlanSessionStatus.PLAN_CONFIRMED.value:
            raise_app_error(409, ErrorCode.SESSION_NOT_ACTIVE, "请先确认并锁定面试计划", trace_id=trace_id)

        confirmed_plan_id = record.get("confirmed_plan_id")
        if not confirmed_plan_id:
            raise_app_error(409, ErrorCode.INTERVIEW_CONFIG_INVALID, "尚未锁定可用计划", trace_id=trace_id)

        user = self.store.decrement_quota(user_id)
        if not user:
            raise_app_error(429, ErrorCode.INTERVIEW_QUOTA_EXHAUSTED, "面试额度不足", trace_id=trace_id)

        plan_record = self.store.get_plan_by_id(confirmed_plan_id)
        plan_json = plan_record["plan_json"]
        configuration = record["configuration"]
        interview_type = str(configuration.get("interview_type", "experienced"))

        runtime_state = build_initial_runtime_state(
            trace_id=trace_id,
            confirmed_plan_id=confirmed_plan_id,
            plan_json=plan_json,
            interview_type=interview_type,
        )
        first_topic = find_topic(plan_json, runtime_state["current_topic_id"])
        if not first_topic:
            raise_app_error(500, ErrorCode.INTERVIEW_BOOTSTRAP_FAILED, "计划主题无效", trace_id=trace_id)

        opening = render_opening_question(first_topic, interview_type=interview_type, trace_id=trace_id)
        runtime_state["last_action"] = "opening"

        record = self._get_session_record(user_id, session_id)
        existing = self._return_if_already_activated(user_id, session_id, record, trace_id=trace_id)
        if existing is not None:
            return existing

        assistant_message = self.store.create_message(
            session_id=session_id,
            role="assistant",
            kind="question",
            content=opening,
            meta={
                "topic_id": first_topic["id"],
                "action": "opening",
                "trace_id": trace_id,
                "is_follow_up": False,
                "source_opening_question": str(first_topic.get("opening_question", "")),
            },
        )

        self.store.update_session(
            session_id,
            status="active",
            workflow_state=runtime_state,
        )

        updated = self._get_session_record(user_id, session_id)
        log_payload(
            logger,
            logging.INFO,
            f"Interview activated: session_id={session_id}",
            {"assistant_message": assistant_message, "runtime_state": runtime_state, "quota_remaining": user["quota_remaining"]},
            trace_id=trace_id,
        )
        return self._serialize_live(updated, start_clock=False)

    def finish_interview(self, user_id: int, session_id: str, *, reason: str = "user_requested") -> dict[str, Any]:
        record = self._reconcile_reply_lock(self._get_session_record(user_id, session_id))
        trace_id = self._trace_id_from_record(record)

        if record["status"] == "evaluating":
            return self._serialize_live(record, start_clock=False)
        if record["status"] == "completed":
            return self._serialize_live(record, start_clock=False)
        if record["status"] != "active":
            raise_app_error(409, ErrorCode.SESSION_NOT_ACTIVE, "当前会话不在进行中", trace_id=trace_id)

        runtime_state = dict(record.get("workflow_state") or {})
        if runtime_state.get("reply_in_progress"):
            raise_app_error(409, ErrorCode.INTERVIEW_REPLY_IN_PROGRESS, "上一条回答仍在处理中，请稍候", trace_id=trace_id)

        current_topic_id = str(runtime_state.get("current_topic_id", ""))
        closing = build_early_finish_message(reason="user")
        assistant_message = self.store.create_message(
            session_id=session_id,
            role="assistant",
            kind="closing",
            content=closing,
            meta={
                "topic_id": current_topic_id,
                "action": "finish",
                "trace_id": trace_id,
                "is_follow_up": False,
                "decision_reason": reason,
                "forced_finish": True,
            },
        )
        runtime_state["last_action"] = "finish"
        runtime_state.pop("reply_in_progress", None)
        runtime_state = freeze_remaining_seconds(runtime_state)
        runtime_state["finish_reason"] = reason
        if current_topic_id:
            completed_ids = list(runtime_state.get("completed_topic_ids") or [])
            if current_topic_id not in completed_ids:
                completed_ids.append(current_topic_id)
            runtime_state["completed_topic_ids"] = completed_ids

        self.store.update_session(
            session_id,
            status="evaluating",
            workflow_state=runtime_state,
        )

        updated = self._get_session_record(user_id, session_id)
        log_payload(
            logger,
            logging.INFO,
            f"Interview finished by user: session_id={session_id}",
            {"assistant_message": assistant_message, "runtime_state": runtime_state},
            trace_id=trace_id,
        )
        return self._serialize_live(updated, start_clock=False)

    def reply_to_interview(self, user_id: int, session_id: str, answer: str) -> dict[str, Any]:
        record = self._reconcile_reply_lock(self._get_session_record(user_id, session_id))
        trace_id = self._trace_id_from_record(record)

        if record["status"] == "evaluating":
            raise_app_error(409, ErrorCode.SESSION_ALREADY_COMPLETED, "当前会话已结束", trace_id=trace_id)
        if record["status"] == "completed":
            raise_app_error(409, ErrorCode.SESSION_ALREADY_COMPLETED, "当前会话已结束", trace_id=trace_id)
        if record["status"] != "active":
            raise_app_error(409, ErrorCode.SESSION_NOT_ACTIVE, "请先开始正式面试", trace_id=trace_id)

        runtime_state = dict(record.get("workflow_state") or {})
        if runtime_state.get("reply_in_progress"):
            raise_app_error(409, ErrorCode.INTERVIEW_REPLY_IN_PROGRESS, "上一条回答仍在处理中，请稍候", trace_id=trace_id)

        runtime_state, _clock_changed = ensure_interview_clock_started(runtime_state)
        runtime_state["reply_in_progress"] = True
        self.store.update_session(session_id, workflow_state=runtime_state)

        try:
            return self._process_reply(user_id, session_id, answer, trace_id)
        except Exception:
            record = self._get_session_record(user_id, session_id)
            failed_state = dict(record.get("workflow_state") or {})
            failed_state.pop("reply_in_progress", None)
            self.store.update_session(session_id, workflow_state=failed_state)
            raise

    def _process_reply(self, user_id: int, session_id: str, answer: str, trace_id: str) -> dict[str, Any]:
        record = self._get_session_record(user_id, session_id)
        runtime_state = dict(record.get("workflow_state") or {})
        confirmed_plan_id = runtime_state.get("confirmed_plan_id") or record.get("confirmed_plan_id")
        if not confirmed_plan_id:
            raise_app_error(409, ErrorCode.INTERVIEW_CONFIG_INVALID, "缺少已锁定计划", trace_id=trace_id)

        plan_record = self.store.get_plan_by_id(str(confirmed_plan_id))
        plan_json = plan_record["plan_json"]
        configuration = record["configuration"]

        current_topic_id = str(runtime_state.get("current_topic_id", ""))
        current_topic = find_topic(plan_json, current_topic_id)
        if not current_topic:
            raise_app_error(500, ErrorCode.INTERVIEW_REPLY_FAILED, "当前主题无效", trace_id=trace_id)

        cleaned_answer = answer.strip()
        user_message = self.store.create_message(
            session_id=session_id,
            role="user",
            kind="answer",
            content=cleaned_answer,
            meta={
                "topic_id": current_topic_id,
                "trace_id": trace_id,
            },
        )

        resume = None
        resume_id = configuration.get("resume_id") or record.get("resume_id")
        if resume_id:
            resume = self.store.get_resume(user_id, str(resume_id))

        all_messages = list(record.get("messages") or []) + [user_message]
        outcome = self.reply_handler.process(
            plan_json=plan_json,
            configuration=configuration,
            resume=resume,
            runtime_state=runtime_state,
            current_topic=current_topic,
            all_messages=all_messages,
            latest_answer=cleaned_answer,
            trace_id=trace_id,
        )

        outcome.runtime_state.pop("reply_in_progress", None)
        if outcome.next_status == "evaluating":
            outcome.runtime_state = freeze_remaining_seconds(outcome.runtime_state)

        assistant_message = self.store.create_message(
            session_id=session_id,
            role="assistant",
            kind=outcome.assistant_kind,
            content=outcome.assistant_content,
            meta=outcome.assistant_meta,
        )

        self.store.update_session(
            session_id,
            status=outcome.next_status,
            workflow_state=outcome.runtime_state,
        )

        updated = self._get_session_record(user_id, session_id)
        log_payload(
            logger,
            logging.INFO,
            f"Interview reply persisted: session_id={session_id}",
            {
                "user_message": user_message,
                "assistant_message": assistant_message,
                "decision": outcome.decision,
                "runtime_state": outcome.runtime_state,
                "status": outcome.next_status,
            },
            trace_id=trace_id,
        )
        return {
            "session": self._serialize_live(updated, start_clock=False),
            "user_message": user_message,
            "assistant_message": assistant_message,
            "decision": outcome.decision,
        }

    async def stream_reply_result(self, payload: dict[str, Any]) -> AsyncIterator[str]:
        try:
            async for chunk in self._stream_reply_result(payload):
                yield chunk
        except Exception as exc:
            logger.exception("Interview reply stream failed")
            yield format_sse(
                "error",
                {
                    "message": "回复处理失败，请刷新页面后重试",
                    "recoverable": True,
                    "detail": str(exc),
                },
            )

    async def _stream_reply_result(self, payload: dict[str, Any]) -> AsyncIterator[str]:
        session = payload["session"]
        assistant_message = payload["assistant_message"]
        progress = session.get("progress") or {}

        yield format_sse(
            "session_state",
            {
                "session_id": session["id"],
                "status": session["status"],
                "progress": progress,
            },
        )
        if progress:
            yield format_sse("progress", progress)

        yield format_sse("message_start", {"session_id": session["id"], "message": assistant_message})
        async for chunk in stream_text(
            assistant_message["content"],
            chunk_size=settings.stream_interview_chunk_size,
            delay_ms=settings.stream_interview_delay_ms,
        ):
            yield format_sse("delta", {"message_id": assistant_message["id"], "delta": chunk})
        yield format_sse("message_end", {"message": assistant_message})
        yield format_sse("done", {"status": session["status"], "session_id": session["id"]})

    def _get_session_record(self, user_id: int, session_id: str) -> dict[str, Any]:
        record = self.store.get_interview_session_record(user_id, session_id)
        if not record:
            raise_app_error(404, ErrorCode.SESSION_NOT_FOUND, "面试会话不存在")
        return record

    def _return_if_already_activated(
        self,
        user_id: int,
        session_id: str,
        record: dict[str, Any],
        *,
        trace_id: str,
    ) -> dict[str, Any] | None:
        if record["status"] == "active":
            logger.info("[trace_id=%s] Interview already active: session_id=%s", trace_id, session_id)
            return self._serialize_live(record, start_clock=False)

        if self._has_opening_message(record.get("messages") or []):
            logger.info(
                "[trace_id=%s] Opening message already exists: session_id=%s",
                trace_id,
                session_id,
            )
            refreshed = self._get_session_record(user_id, session_id)
            return self._serialize_live(refreshed, start_clock=False)

        return None

    @staticmethod
    def _has_opening_message(messages: list[dict[str, Any]]) -> bool:
        return any(str((message.get("meta") or {}).get("action")) == "opening" for message in messages)

    def _serialize_live(self, record: dict[str, Any], *, start_clock: bool = False) -> dict[str, Any]:
        confirmed_plan_id = record.get("confirmed_plan_id")
        if not confirmed_plan_id:
            raise_app_error(409, ErrorCode.INTERVIEW_CONFIG_INVALID, "缺少已锁定计划")

        plan_record = self.store.get_plan_by_id(str(confirmed_plan_id))
        runtime_state = dict(record.get("workflow_state") or {})
        if start_clock and record.get("status") == "active":
            runtime_state, clock_changed = ensure_interview_clock_started(runtime_state)
            if clock_changed:
                self.store.update_session(str(record["id"]), workflow_state=runtime_state)
                record = self._get_session_record(int(record["user_id"]), str(record["id"]))
                runtime_state = dict(record.get("workflow_state") or {})
        return serialize_live_session_detail(
            session_row=record,
            configuration=record["configuration"],
            plan_record=plan_record,
            messages=record.get("messages") or [],
            runtime_state=runtime_state,
        )

    def _reconcile_reply_lock(self, record: dict[str, Any]) -> dict[str, Any]:
        runtime_state = dict(record.get("workflow_state") or {})
        if not runtime_state.get("reply_in_progress"):
            return record

        messages = record.get("messages") or []
        should_clear = False
        if messages and messages[-1].get("role") == "assistant":
            should_clear = True
        elif self._reply_lock_is_stale(record.get("updated_at")):
            should_clear = True
            logger.warning(
                "[trace_id=%s] Cleared stale reply_in_progress: session_id=%s",
                self._trace_id_from_record(record),
                record.get("id"),
            )

        if not should_clear:
            return record

        runtime_state.pop("reply_in_progress", None)
        self.store.update_session(str(record["id"]), workflow_state=runtime_state)
        refreshed = self._get_session_record(int(record["user_id"]), str(record["id"]))
        return refreshed

    @staticmethod
    def _reply_lock_is_stale(updated_at: str | None) -> bool:
        if not updated_at:
            return True
        try:
            parsed = datetime.fromisoformat(str(updated_at))
        except ValueError:
            return True
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()
        return elapsed >= settings.interview_stale_reply_lock_seconds

    @staticmethod
    def _trace_id_from_record(record: dict[str, Any]) -> str:
        workflow_state = record.get("workflow_state") or {}
        return str(workflow_state.get("trace_id") or new_trace_id("interview"))
