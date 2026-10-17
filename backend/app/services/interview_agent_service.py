"""动态面试编排服务。"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from app.agent.interview.opening import render_opening_question
from app.agent.interview.transitions import build_early_finish_message
from app.core.config import settings
from app.core.errors import ErrorCode, raise_app_error
from app.core.logging_utils import log_payload, new_trace_id
from app.core.session_state import SessionState, assert_transition, coerce
from app.core.streaming import format_sse, stream_text
from app.db.store import Store
from app.db.transaction import transaction
from app.services.interview.reply_handler import InterviewReplyHandler
from app.services.interview.boundaries import freeze_remaining_seconds
from app.services.interview.runtime_state import (
    build_initial_runtime_state,
    ensure_interview_clock_started,
    find_topic,
)
from app.services.interview.serialization import serialize_live_session_detail


logger = logging.getLogger("uvicorn.error")

# 1.3：分布式锁 TTL（秒）。失败路径由数据库过期兜底。
LOCK_TTL_SECONDS = 300


class InterviewAgentService:
    def __init__(self) -> None:
        self.store = Store()
        self.reply_handler = InterviewReplyHandler()

    def is_v2_session(self, user_id: int, session_id: str) -> bool:
        record = self.store.get_interview_session_record(user_id, session_id)
        return record is not None

    def get_live_session_detail(self, user_id: int, session_id: str) -> dict[str, Any] | None:
        record = self._get_session_record(user_id, session_id)
        # 1.1：用 coerce 取代字符串字面量比较。
        try:
            current_state = coerce(record["status"])
        except Exception:
            return None
        if current_state not in {SessionState.ACTIVE, SessionState.EVALUATING, SessionState.COMPLETED}:
            return None
        return self._serialize_live(record, start_clock=True)

    def pause_interview(self, user_id: int, session_id: str) -> dict[str, Any]:
        """v1.1: 离开页面冻结面试计时。记录 paused_at；不消耗额度、不改状态。"""
        record = self._get_session_record(user_id, session_id)
        # 1.1：状态判断走 coerce。
        if coerce(record["status"]) != SessionState.ACTIVE:
            return {
                "session_id": session_id,
                "paused": False,
                "reason": f"status_{record['status']}",
                "remaining_seconds": None,
            }
        runtime_state = dict(record.get("workflow_state") or {})
        if not runtime_state.get("paused_at"):
            runtime_state["paused_at"] = datetime.now(timezone.utc).isoformat()
            self.store.update_session(session_id, workflow_state=runtime_state)
        remaining = self._compute_remaining_seconds(runtime_state)
        return {
            "session_id": session_id,
            "paused": True,
            "paused_at": runtime_state.get("paused_at"),
            "remaining_seconds": remaining,
        }

    def resume_interview(self, user_id: int, session_id: str) -> dict[str, Any]:
        """v1.1: 回到页面恢复面试计时。累计 paused 区间，remaining_seconds 跳过。"""
        record = self._get_session_record(user_id, session_id)
        runtime_state = dict(record.get("workflow_state") or {})
        paused_at = runtime_state.get("paused_at")
        if paused_at:
            try:
                start = datetime.fromisoformat(str(paused_at).replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                delta = max(0, int((now - start).total_seconds()))
            except Exception:
                delta = 0
            if delta > 0:
                runtime_state["total_paused_seconds"] = int(runtime_state.get("total_paused_seconds") or 0) + delta
            runtime_state.pop("paused_at", None)
            self.store.update_session(session_id, workflow_state=runtime_state)
        remaining = self._compute_remaining_seconds(runtime_state)
        return {
            "session_id": session_id,
            "paused": False,
            "total_paused_seconds": runtime_state.get("total_paused_seconds", 0),
            "remaining_seconds": remaining,
        }

    def _compute_remaining_seconds(self, runtime_state: dict[str, Any]) -> int | None:
        """v1.1: 用 workflow_state 算 remaining_seconds，已减 total_paused_seconds。"""
        from app.services.interview.boundaries import remaining_seconds
        deadline = str(runtime_state.get("deadline_at") or "")
        rest = remaining_seconds(deadline)
        if rest is None:
            return None
        paused = int(runtime_state.get("total_paused_seconds") or 0)
        # 当前若正 paused，再加实时 paused 区间
        if runtime_state.get("paused_at"):
            try:
                start = datetime.fromisoformat(str(runtime_state["paused_at"]).replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                paused += max(0, int((now - start).total_seconds()))
            except Exception:
                pass
        return max(0, rest - paused)

    def activate_interview(self, user_id: int, session_id: str) -> dict[str, Any]:
        record = self._get_session_record(user_id, session_id)
        trace_id = new_trace_id("interview")

        # 1.1：用 coerce 取代字符串字面量比较。
        current_state = coerce(record["status"])
        if current_state in {SessionState.EVALUATING, SessionState.COMPLETED}:
            raise_app_error(409, ErrorCode.SESSION_ALREADY_COMPLETED, "当前会话已结束", trace_id=trace_id)

        existing_live = self._return_if_already_activated(user_id, session_id, record, trace_id=trace_id)
        if existing_live:
            return existing_live

        if current_state != SessionState.PLAN_CONFIRMED:
            raise_app_error(409, ErrorCode.SESSION_NOT_ACTIVE, "请先确认并锁定面试计划", trace_id=trace_id)
        # 1.1：合法转换 PLAN_CONFIRMED -> ACTIVE。
        assert_transition(current_state, SessionState.ACTIVE)

        confirmed_plan_id = record.get("confirmed_plan_id")
        if not confirmed_plan_id:
            raise_app_error(409, ErrorCode.INTERVIEW_CONFIG_INVALID, "尚未锁定可用计划", trace_id=trace_id)

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

        # 1.2：opening 不再调用 LLM，直接读 plan 的 opening_question。
        opening = render_opening_question(first_topic, interview_type=interview_type, trace_id=trace_id)
        runtime_state["last_action"] = "opening"

        # 1.2：单事务：扣额度（audit） + 写开场消息 + 切状态 + 改 runtime_state。
        # 任一失败整体回滚，额度不丢。
        try:
            with transaction() as conn:
                user = self.store.get_user_by_id(user_id)
                if not user:
                    raise_app_error(404, ErrorCode.USER_NOT_FOUND, "用户不存在", trace_id=trace_id)
                # v2.2：订阅用户跳过额度检查（decrement_quota_in_conn 内部会再确认一次）
                if not self.store.is_subscription_active(user) and int(user["quota_remaining"]) <= 0:
                    raise_app_error(
                        429,
                        ErrorCode.INTERVIEW_QUOTA_EXHAUSTED,
                        "免费额度已用完，充值 20 元可获得 5 次面试",
                        trace_id=trace_id,
                    )
                self.store.decrement_quota_in_conn(
                    conn,
                    user_id,
                    session_id=session_id,
                    reason="interview_activate",
                )
                assistant_message = self.store.create_message_in_conn(
                    conn,
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
                self.store.update_session_in_conn(
                    conn,
                    session_id,
                    status=SessionState.ACTIVE.value,
                    workflow_state=runtime_state,
                )
        except Exception as exc:
            from app.core.events import rollback_event
            rollback_event(
                logger,
                "interview.activate.rolled_back",
                trace_id=trace_id,
                session_id=session_id,
                user_id=user_id,
                error=str(exc),
            )
            raise

        from app.core.events import commit_event
        commit_event(
            logger,
            "interview.activate.committed",
            trace_id=trace_id,
            session_id=session_id,
            user_id=user_id,
            first_topic_id=first_topic["id"],
        )

        user = self.store.get_user_by_id(user_id)
        updated = self._get_session_record(user_id, session_id)
        log_payload(
            logger,
            logging.INFO,
            f"Interview activated (atomic): session_id={session_id}",
            {"assistant_message": assistant_message, "runtime_state": runtime_state, "quota_remaining": (user or {}).get("quota_remaining")},
            trace_id=trace_id,
        )
        return self._serialize_live(updated, start_clock=False)

    def finish_interview(self, user_id: int, session_id: str, *, reason: str = "user_requested") -> dict[str, Any]:
        record = self._get_session_record(user_id, session_id)
        trace_id = self._trace_id_from_record(record)
        # 1.1：状态判断统一走 coerce + assert_transition。
        current_state = coerce(record["status"])
        if current_state == SessionState.EVALUATING:
            return self._serialize_live(record, start_clock=False)
        if current_state == SessionState.COMPLETED:
            return self._serialize_live(record, start_clock=False)
        if current_state != SessionState.ACTIVE:
            raise_app_error(409, ErrorCode.SESSION_NOT_ACTIVE, "当前会话不在进行中", trace_id=trace_id)
        assert_transition(current_state, SessionState.EVALUATING)

        # 1.3：检查 session_locks 表。仍有 lock 说明上一条还在处理中。
        active_lock = self.store.get_session_lock(session_id)
        if active_lock is not None:
            raise_app_error(409, ErrorCode.INTERVIEW_REPLY_IN_PROGRESS, "上一条回答仍在处理中，请稍候", trace_id=trace_id)

        runtime_state = dict(record.get("workflow_state") or {})
        # 1.2 根因：activate 没启动 clock 时 finish 拿不到 deadline。
        configured_duration = int(record.get("configuration", {}).get("duration_minutes", 45) or 45)
        runtime_state, _ = ensure_interview_clock_started(runtime_state, duration_minutes=configured_duration)
        current_topic_id = str(runtime_state.get("current_topic_id", ""))
        closing = build_early_finish_message(reason="user")
        # 1.2：单事务写 closing + 切 status + 改 workflow_state。
        with transaction() as conn:
            assistant_message = self.store.create_message_in_conn(
                conn,
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
            runtime_state = freeze_remaining_seconds(runtime_state)
            runtime_state["finish_reason"] = reason
            if current_topic_id:
                completed_ids = list(runtime_state.get("completed_topic_ids") or [])
                if current_topic_id not in completed_ids:
                    completed_ids.append(current_topic_id)
                runtime_state["completed_topic_ids"] = completed_ids
            self.store.update_session_in_conn(
                conn,
                session_id,
                status=SessionState.EVALUATING.value,
                workflow_state=runtime_state,
            )

        updated = self._get_session_record(user_id, session_id)
        log_payload(
            logger,
            logging.INFO,
            f"Interview finished by user (atomic): session_id={session_id}",
            {"assistant_message": assistant_message, "runtime_state": runtime_state},
            trace_id=trace_id,
        )
        return self._serialize_live(updated, start_clock=False)

    def reply_to_interview(self, user_id: int, session_id: str, answer: str) -> dict[str, Any]:
        record = self._get_session_record(user_id, session_id)
        trace_id = self._trace_id_from_record(record)
        # 1.1：状态判断统一走 coerce。
        current_state = coerce(record["status"])
        if current_state in {SessionState.EVALUATING, SessionState.COMPLETED}:
            raise_app_error(409, ErrorCode.SESSION_ALREADY_COMPLETED, "当前会话已结束", trace_id=trace_id)
        if current_state != SessionState.ACTIVE:
            raise_app_error(409, ErrorCode.SESSION_NOT_ACTIVE, "请先开始正式面试", trace_id=trace_id)

        # 1.3：分布式锁。request_id 缺失时用 trace_id 当 token。
        lock_token = f"reply:{trace_id}"
        lock = self.store.acquire_session_lock(
            session_id,
            lock_token=lock_token,
            ttl_seconds=LOCK_TTL_SECONDS,
            lock_type="session",
        )
        if lock is None or lock.get("locked"):
            raise_app_error(409, ErrorCode.INTERVIEW_REPLY_IN_PROGRESS, "上一条回答仍在处理中，请稍候", trace_id=trace_id)

        try:
            return self._process_reply(user_id, session_id, answer, trace_id)
        finally:
            self.store.release_session_lock(session_id, lock_token=lock_token, lock_type="session")

    def _process_reply(self, user_id: int, session_id: str, answer: str, trace_id: str) -> dict[str, Any]:
        record = self._get_session_record(user_id, session_id)
        runtime_state = dict(record.get("workflow_state") or {})
        runtime_state, _clock_changed = ensure_interview_clock_started(runtime_state)
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
        # 1.2：单事务写 user_message + 调图 + 写 assistant_message + 改 session。
        with transaction() as conn:
            user_message = self.store.create_message_in_conn(
                conn,
                session_id=session_id,
                role="user",
                kind="answer",
                content=cleaned_answer,
                meta={"topic_id": current_topic_id, "trace_id": trace_id},
            )

            # 临时把最新消息列表带进去给 handler
            record_in_tx = self.store.get_interview_session_record(user_id, session_id)
            all_messages = list(record_in_tx.get("messages") or []) + [user_message]
            resume = None
            resume_id = configuration.get("resume_id") or record_in_tx.get("resume_id")
            if resume_id:
                resume = self.store.get_resume(user_id, str(resume_id))
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

            # 1.4：若 graph 端 precheck 命中边界并要求跳过 user_message，则删除刚写的
            # user_message。这能保持"硬边界触发时不写 user_message"的语义。
            decision = outcome.decision or {}
            finish_reasons = {
                "max_answer_rounds",
                "deadline_reached",
                "topic_round_limit_last_topic",
                "probe_limit_last_topic",
                "wrap_up_required_topics_covered",
                "wrap_up_no_more_topics",
            }
            if decision.get("reason") in finish_reasons and outcome.next_status == "evaluating":
                # 边界类 finish：只保留 assistant 关闭消息。
                conn.execute(
                    "DELETE FROM messages WHERE id = ?", (user_message["id"],),
                )
                # 用 plan 合规消息代替 user_message（占位）
                outcome.assistant_meta = {
                    **outcome.assistant_meta,
                    "boundary_skip_user": True,
                }

            # 1.1：next_status 必须是合法目标。
            next_state = coerce(outcome.next_status)
            assert_transition(SessionState.ACTIVE, next_state)

            if next_state == SessionState.EVALUATING:
                outcome.runtime_state = freeze_remaining_seconds(outcome.runtime_state)
            assistant_message = self.store.create_message_in_conn(
                conn,
                session_id=session_id,
                role="assistant",
                kind=outcome.assistant_kind,
                content=outcome.assistant_content,
                meta=outcome.assistant_meta,
            )
            self.store.update_session_in_conn(
                conn,
                session_id,
                status=next_state.value,
                workflow_state=outcome.runtime_state,
            )

        updated = self._get_session_record(user_id, session_id)
        log_payload(
            logger,
            logging.INFO,
            f"Interview reply persisted (atomic): session_id={session_id}",
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

    async def reply_to_interview_streaming(
        self,
        user_id: int,
        session_id: str,
        answer: str,
        request_id: str | None = None,
    ) -> tuple[dict[str, Any], "asyncio.Queue[str]"]:
        """A3：流式回复。

        - 复用 reply_to_interview 的所有校验（lock、状态、quota）
        - 在异步路径中跑 LangGraph，把每次 LLM 输出切片推到 queue
        - SSE 端从 queue 读 delta
        - 落库时机仍为"末尾"，保证数据一致性
        """
        import asyncio
        from app.services.interview.reply_handler import InterviewReplyHandler

        record = self._get_session_record(user_id, session_id)
        trace_id = self._trace_id_from_record(record)
        # 1.1：状态判断统一走 coerce。
        current_state = coerce(record["status"])
        if current_state in {SessionState.EVALUATING, SessionState.COMPLETED}:
            raise_app_error(409, ErrorCode.SESSION_ALREADY_COMPLETED, "当前会话已结束", trace_id=trace_id)
        if current_state != SessionState.ACTIVE:
            raise_app_error(409, ErrorCode.SESSION_NOT_ACTIVE, "请先开始正式面试", trace_id=trace_id)

        # 1.3：分布式锁。request_id 优先作为 lock_token。
        lock_token = request_id or f"reply:{trace_id}"
        lock = self.store.acquire_session_lock(
            session_id,
            lock_token=lock_token,
            ttl_seconds=LOCK_TTL_SECONDS,
            lock_type="session",
        )
        if lock is None or lock.get("locked"):
            raise_app_error(409, ErrorCode.INTERVIEW_REPLY_IN_PROGRESS, "上一条回答仍在处理中，请稍候", trace_id=trace_id)

        # 幂等：同 request_id 复用 user_message + 配对的 assistant_message（v2.3）
        if request_id:
            user_msg, assistant_msg = self.store.find_message_pair_by_request_id(
                session_id, request_id,
            )
            if user_msg and user_msg.get("role") == "user":
                if not assistant_msg:
                    # 还没有 assistant（可能上一次中断），回退到 user_message 上下文
                    self.store.release_session_lock(session_id, lock_token=lock_token, lock_type="session")
                    raise_app_error(
                        409,
                        ErrorCode.INTERVIEW_REPLY_IN_PROGRESS,
                        "上一条回答还在处理中，请稍候重试",
                        trace_id=trace_id,
                    )
                updated = self._get_session_record(user_id, session_id)
                queue: "asyncio.Queue[str]" = asyncio.Queue()
                await queue.put(assistant_msg.get("content", ""))
                await queue.put("__DONE__")
                self.store.release_session_lock(
                    session_id, lock_token=lock_token, lock_type="session",
                )
                return {
                    "session": self._serialize_live(updated, start_clock=False),
                    "user_message": user_msg,
                    "assistant_message": assistant_msg,
                    "decision": {},
                    "supports_streaming": False,
                }, queue

        record = self._get_session_record(user_id, session_id)
        runtime_state = dict(record.get("workflow_state") or {})
        runtime_state, _clock_changed = ensure_interview_clock_started(runtime_state)
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
        # 1.2：先写 user_message（事务内），拿到 user_message 后再异步跑图，最后事务内落 assistant + session。
        with transaction() as conn:
            user_message = self.store.create_message_in_conn(
                conn,
                session_id=session_id,
                role="user",
                kind="answer",
                content=cleaned_answer,
                meta={"topic_id": current_topic_id, "trace_id": trace_id, "request_id": request_id},
                request_id=request_id,
            )

        queue = asyncio.Queue(maxsize=64)
        resume = None
        resume_id = configuration.get("resume_id") or record.get("resume_id")
        if resume_id:
            resume = self.store.get_resume(user_id, str(resume_id))

        record_after_user = self._get_session_record(user_id, session_id)
        all_messages = list(record_after_user.get("messages") or [])
        handler = InterviewReplyHandler()
        try:
            outcome, _collected = await handler.process_streaming(
                plan_json=plan_json,
                configuration=configuration,
                resume=resume,
                runtime_state=runtime_state,
                current_topic=current_topic,
                all_messages=all_messages,
                latest_answer=cleaned_answer,
                trace_id=trace_id,
                delta_queue=queue,
            )
        except Exception:
            logger.exception("reply_to_interview_streaming failed, releasing lock")
            self.store.release_session_lock(session_id, lock_token=lock_token, lock_type="session")
            raise

        outcome_runtime = dict(outcome.runtime_state)
        next_state = coerce(outcome.next_status)
        assert_transition(SessionState.ACTIVE, next_state)
        if next_state == SessionState.EVALUATING:
            outcome_runtime = freeze_remaining_seconds(outcome_runtime)

        # 1.4：边界类 finish → 删除刚写的 user_message（与同步路径一致）。
        decision = outcome.decision or {}
        if (
            decision.get("reason") in {"max_answer_rounds", "deadline_reached"}
            and outcome.next_status == "evaluating"
        ):
            with transaction() as conn:
                conn.execute(
                    "DELETE FROM messages WHERE id = ?", (user_message["id"],),
                )
            outcome.assistant_meta = {
                **outcome.assistant_meta,
                "boundary_skip_user": True,
            }

        # 1.2：末尾事务：写 assistant + 改 session。
        try:
            with transaction() as conn:
                assistant_message = self.store.create_message_in_conn(
                    conn,
                    session_id=session_id,
                    role="assistant",
                    kind=outcome.assistant_kind,
                    content=outcome.assistant_content,
                    meta=outcome.assistant_meta,
                )
                self.store.update_session_in_conn(
                    conn,
                    session_id,
                    status=next_state.value,
                    workflow_state=outcome_runtime,
                )
        except Exception:
            self.store.release_session_lock(session_id, lock_token=lock_token, lock_type="session")
            raise
        self.store.release_session_lock(session_id, lock_token=lock_token, lock_type="session")
        updated = self._get_session_record(user_id, session_id)

        payload = {
            "session": self._serialize_live(updated, start_clock=False),
            "user_message": user_message,
            "assistant_message": assistant_message,
            "decision": outcome.decision,
            "supports_streaming": True,
        }
        await queue.put("__DONE__")
        return payload, queue

    def _latest_assistant_message(self, user_id: int, session_id: str) -> dict[str, Any]:
        record = self.store.get_interview_session_record(user_id, session_id)
        if not record:
            return {}
        messages = record.get("messages") or []
        for m in reversed(messages):
            if m.get("role") == "assistant":
                return m
        return {}

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
            # v2.3: error 事件后立即结束 generator，避免 client 误认为仍有更多事件。
            return

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

        # A3：若上游传入了 LLM delta queue，按真流推送；否则降级分块回放
        delta_queue = payload.get("delta_queue")
        if delta_queue is not None:
            emitted = False
            try:
                while True:
                    delta = await delta_queue.get()
                    if delta == "__DONE__":
                        break
                    if not delta:
                        continue
                    emitted = True
                    yield format_sse(
                        "delta",
                        {"message_id": assistant_message["id"], "delta": delta},
                    )
            except Exception as exc:
                logger.warning("A3 stream drain failed, falling back to chunked replay: %s", exc)
                if not emitted:
                    async for chunk in stream_text(
                        assistant_message["content"],
                        chunk_size=settings.stream_interview_chunk_size,
                        delay_ms=settings.stream_interview_delay_ms,
                    ):
                        yield format_sse("delta", {"message_id": assistant_message["id"], "delta": chunk})
        else:
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
        # 1.1：状态判断走 coerce。
        try:
            current_state = coerce(record["status"])
        except Exception:
            return None
        if current_state == SessionState.ACTIVE:
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
        # 1.1：状态判断走 coerce。
        try:
            current_state = coerce(record.get("status", ""))
        except Exception:
            current_state = None
        if start_clock and current_state == SessionState.ACTIVE:
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

    # 1.3：_reconcile_reply_lock / _reply_lock_is_stale 已被 session_locks 表取代。
    # 锁过期由数据库 expires_at 兜底。故意删除以避免双源状态。

    @staticmethod
    def _trace_id_from_record(record: dict[str, Any]) -> str:
        workflow_state = record.get("workflow_state") or {}
        return str(workflow_state.get("trace_id") or new_trace_id("interview"))
