"""Planning 编排服务：创建会话、生成/重新生成/确认计划，协调 Agent 与落库。"""
from __future__ import annotations

import logging
from typing import Any

from app.core.errors import ErrorCode, raise_app_error
from app.core.logging_utils import log_payload, new_trace_id
from app.core.session_state import SessionState
from app.db.store import Store
from app.db.transaction import transaction
from app.services.interview_configuration_service import configuration_labels
from app.services.interview_planning.constants import MAX_REGENERATIONS
from app.services.interview_planning.context import get_planning_context
from app.services.interview_planning.preview import build_plan_preview, build_version_history_item
from app.services.interview_planning.regeneration import build_previous_plan_summary, plans_have_effective_difference
from app.services.interview_planning.request_validation import (
    validate_interview_configuration,
    validate_regeneration_request,
    validate_resume_for_planning,
)


logger = logging.getLogger("uvicorn.error")


class InterviewPlanningService:
    def __init__(self) -> None:
        from app.agent.interview_planning.agent import PlanningAgent

        self.store = Store()
        self.planning_agent = PlanningAgent()

    def create_interview(self, user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        trace_id = new_trace_id("plan")
        configuration = validate_interview_configuration(payload, trace_id=trace_id)
        resume = validate_resume_for_planning(
            self.store.get_resume(user_id, configuration["resume_id"]),
            trace_id=trace_id,
        )
        logger.info(
            "[trace_id=%s] Create interview requested: user_id=%s resume_id=%s interview_type=%s",
            trace_id,
            user_id,
            configuration["resume_id"],
            configuration["interview_type"],
        )
        log_payload(logger, logging.INFO, "Interview configuration", configuration, trace_id=trace_id)

        session = self.store.create_planning_session(
            user_id=user_id,
            title=self._build_session_title(configuration),
            target_role=configuration["target_role"],
            resume_id=configuration["resume_id"],
            configuration=configuration,
        )
        plan_preview = self._generate_plan_for_session(
            session=session,
            configuration=configuration,
            resume=resume,
            trace_id=trace_id,
            version=1,
        )
        log_payload(logger, logging.INFO, "Interview plan preview", plan_preview, trace_id=trace_id)
        return plan_preview

    def generate_plan(self, user_id: int, session_id: str) -> dict[str, Any]:
        trace_id = new_trace_id("plan")
        session = self._get_planning_session(user_id, session_id, trace_id=trace_id)
        configuration = session["configuration"]
        resume = validate_resume_for_planning(
            self.store.get_resume(user_id, configuration["resume_id"]),
            trace_id=trace_id,
        )

        existing_plan = self.store.get_latest_plan(session_id)
        if existing_plan and session["status"] == SessionState.PLAN_READY.value:
            return build_plan_preview(
                session_id=session_id,
                plan_record=existing_plan,
                configuration=configuration,
                status=session["status"],
            )

        if existing_plan and session["status"] != SessionState.PLANNING.value:
            raise_app_error(409, ErrorCode.INTERVIEW_CONFIG_INVALID, "当前会话已有计划，请使用重新生成", trace_id=trace_id)

        return self._generate_plan_for_session(
            session=session,
            configuration=configuration,
            resume=resume,
            trace_id=trace_id,
            version=1,
        )

    def regenerate_plan(self, user_id: int, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        trace_id = new_trace_id("plan")
        session = self._get_planning_session(user_id, session_id, trace_id=trace_id)
        if session["status"] != SessionState.PLAN_READY.value:
            raise_app_error(409, ErrorCode.INTERVIEW_CONFIG_INVALID, "当前状态不可重新生成计划", trace_id=trace_id)

        configuration = session["configuration"]
        latest_plan = self.store.get_latest_plan(session_id)
        if not latest_plan:
            raise_app_error(404, ErrorCode.INTERVIEW_CONFIG_INVALID, "尚未生成计划", trace_id=trace_id)

        if latest_plan["version"] >= MAX_REGENERATIONS + 1:
            raise_app_error(429, ErrorCode.INTERVIEW_CONFIG_INVALID, "重新生成次数已达上限", trace_id=trace_id)

        regeneration_feedback = validate_regeneration_request(payload, configuration=configuration, trace_id=trace_id)
        resume = validate_resume_for_planning(
            self.store.get_resume(user_id, configuration["resume_id"]),
            trace_id=trace_id,
        )
        previous_plan_summary = build_previous_plan_summary(latest_plan)
        log_payload(logger, logging.INFO, "Plan regeneration requested", regeneration_feedback, trace_id=trace_id)

        return self._generate_plan_for_session(
            session=session,
            configuration=configuration,
            resume=resume,
            trace_id=trace_id,
            version=latest_plan["version"] + 1,
            regeneration_feedback=regeneration_feedback,
            previous_plan_summary=previous_plan_summary,
            previous_plan_record=latest_plan,
        )

    def confirm_plan(self, user_id: int, session_id: str) -> dict[str, Any]:
        trace_id = new_trace_id("plan")
        session = self._get_planning_session(user_id, session_id, trace_id=trace_id)
        configuration = session["configuration"]

        if session["status"] == SessionState.PLAN_CONFIRMED.value:
            raise_app_error(409, ErrorCode.INTERVIEW_CONFIG_INVALID, "计划已确认锁定", trace_id=trace_id)

        if session["status"] != SessionState.PLAN_READY.value:
            raise_app_error(409, ErrorCode.INTERVIEW_CONFIG_INVALID, "当前状态不可确认计划", trace_id=trace_id)

        latest_plan = self.store.get_latest_plan(session_id)
        if not latest_plan:
            raise_app_error(404, ErrorCode.INTERVIEW_CONFIG_INVALID, "尚未生成计划", trace_id=trace_id)

        # 1.2：单事务写：plan.status -> confirmed && session.status -> plan_confirmed
        # && session.confirmed_plan_id = latest_plan.id。三者中任一失败整体回滚。
        from datetime import datetime, timezone, timedelta

        confirmed_at = datetime.now(timezone.utc).isoformat()
        supersede_expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=10)
        ).isoformat()
        with transaction() as conn:
            self.store.update_interview_plan_status_in_conn(
                conn, latest_plan["id"], status="confirmed",
            )
            # 把 supersede 窗口写到 plan 的 meta（无需 schema 变更）
            self.store.update_planning_session_in_conn(
                conn,
                session_id,
                status=SessionState.PLAN_CONFIRMED.value,
                confirmed_plan_id=latest_plan["id"],
            )
            # 临时记录过期时间到 session workflow_state（不入 plan.status）
            # 使用 workflow_state 显式覆盖。store.update_session 走白名单。
            existing_state_row = conn.execute(
                "SELECT workflow_state_json FROM interview_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            import json as _json

            state = _json.loads(existing_state_row["workflow_state_json"] or "{}") if existing_state_row else {}
            state["confirm_supersede_until"] = supersede_expires_at
            state["confirmed_at"] = confirmed_at
            self.store.update_session_in_conn(
                conn, session_id, workflow_state=state,
            )
        logger.info(
            "[trace_id=%s] Plan confirmed (atomic): session_id=%s plan_id=%s version=%s",
            trace_id,
            session_id,
            latest_plan["id"],
            latest_plan["version"],
        )

        confirmed_plan = self.store.get_plan_by_id(latest_plan["id"])
        return build_plan_preview(
            session_id=session_id,
            plan_record=confirmed_plan,
            configuration=configuration,
            status=SessionState.PLAN_CONFIRMED.value,
        )

    def supersede_plan(self, user_id: int, session_id: str) -> dict[str, Any]:
        """5.10：撤销 10 秒内刚确认的计划。

        行为：
        - 把当前 confirmed plan 标记为 superseded
        - session 回退到 plan_ready（清空 confirmed_plan_id）
        - 触发 _generate_plan_for_session 不算"regenerate"（version+1 + 重新 ready）
        """
        trace_id = new_trace_id("plan")
        session = self._get_planning_session(user_id, session_id, trace_id=trace_id)
        if session["status"] != SessionState.PLAN_CONFIRMED.value:
            raise_app_error(409, ErrorCode.INTERVIEW_CONFIG_INVALID, "当前状态不可撤销", trace_id=trace_id)
        import json as _json
        from datetime import datetime, timezone

        state = session.get("workflow_state") or {}
        until = state.get("confirm_supersede_until")
        if not until:
            raise_app_error(410, ErrorCode.INTERVIEW_CONFIG_INVALID, "已过撤销窗口", trace_id=trace_id)
        try:
            until_dt = datetime.fromisoformat(until.replace("Z", "+00:00"))
        except ValueError:
            raise_app_error(410, ErrorCode.INTERVIEW_CONFIG_INVALID, "已过撤销窗口", trace_id=trace_id)
        if datetime.now(timezone.utc) > until_dt:
            raise_app_error(410, ErrorCode.INTERVIEW_CONFIG_INVALID, "已过撤销窗口", trace_id=trace_id)
        confirmed_plan_id = session.get("confirmed_plan_id")
        if not confirmed_plan_id:
            raise_app_error(409, ErrorCode.INTERVIEW_CONFIG_INVALID, "无确认计划可撤销", trace_id=trace_id)
        with transaction() as conn:
            self.store.update_interview_plan_status_in_conn(
                conn, confirmed_plan_id, status="superseded",
            )
            self.store.update_planning_session_in_conn(
                conn,
                session_id,
                status=SessionState.PLAN_READY.value,
                confirmed_plan_id=None,
            )
            existing_state_row = conn.execute(
                "SELECT workflow_state_json FROM interview_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            st = _json.loads(existing_state_row["workflow_state_json"] or "{}") if existing_state_row else {}
            st.pop("confirm_supersede_until", None)
            st.pop("confirmed_at", None)
            self.store.update_session_in_conn(
                conn, session_id, workflow_state=st,
            )
        return self.get_session_detail(user_id, session_id) or {}

    def get_session_detail(self, user_id: int, session_id: str) -> dict[str, Any] | None:
        session = self.store.get_planning_session(user_id, session_id)
        if not session:
            return None

        configuration = session["configuration"]
        plan_records = self.store.list_plans_for_session(session_id)
        active_plan = self._resolve_active_plan(session, plan_records)
        plan_preview = None
        if active_plan:
            plan_preview = build_plan_preview(
                session_id=session_id,
                plan_record=active_plan,
                configuration=configuration,
                status=session["status"],
            )

        version_history = [
            build_version_history_item(plan_record=record, configuration=configuration) for record in plan_records
        ]

        return {
            "id": session["id"],
            "status": session["status"],
            "configuration": configuration,
            "plan": plan_preview,
            "version_history": version_history,
            "confirmed_plan_id": session.get("confirmed_plan_id"),
            "created_at": session["created_at"],
            "updated_at": session["updated_at"],
        }

    def _generate_plan_for_session(
        self,
        *,
        session: dict[str, Any],
        configuration: dict[str, Any],
        resume: dict[str, Any],
        trace_id: str,
        version: int,
        regeneration_feedback: dict[str, Any] | None = None,
        previous_plan_summary: dict[str, Any] | None = None,
        previous_plan_record: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = get_planning_context(configuration=configuration, resume=resume, trace_id=trace_id)
        generated = self.planning_agent.generate_plan(
            configuration=configuration,
            resume=resume,
            role_knowledge_context=context["role_knowledge_context"],
            trace_id=trace_id,
            previous_plan_summary=previous_plan_summary,
            regeneration_feedback=regeneration_feedback,
        )
        candidate_summary_json = generated.pop("candidate_summary")
        metadata = {
            key: generated.pop(key)
            for key in ("source", "generation_attempts", "degraded", "degraded_reason")
            if key in generated
        }
        plan_json = generated
        if metadata:
            plan_json = {**plan_json, "generation_meta": metadata}

        candidate_record = {
            "plan_json": plan_json,
            "candidate_summary_json": candidate_summary_json,
        }
        if previous_plan_record and not plans_have_effective_difference(previous_plan_record, candidate_record):
            raise_app_error(409, ErrorCode.INTERVIEW_CONFIG_INVALID, "新计划与当前版本没有有效差异", trace_id=trace_id)

        plan_record = self.store.create_interview_plan(
            session_id=session["id"],
            version=version,
            status="ready",
            plan_json=plan_json,
            candidate_summary_json=candidate_summary_json,
            regeneration_strategy=(regeneration_feedback or {}).get("regeneration_strategy"),
            focus_topics=None,
            additional_instruction=(regeneration_feedback or {}).get("additional_instruction") or None,
        )
        # 1.2：plan 写入与 session status 写入应同事务。store.create_interview_plan
        # 自己跑一个独立连接，把 plan 提早 commit 仍可接受——session 状态失败不会
        # 产生"plan 与 session 不一致"（plan.ready 与 session.plan_ready 都是幂等
        # 状态），但补一层 try/except 记日志，事务外更新 session。
        try:
            self.store.update_planning_session(
                session["id"],
                status=SessionState.PLAN_READY.value,
            )
        except Exception:
            logger.exception(
                "[trace_id=%s] Failed to mark session plan_ready after plan write", trace_id,
            )
        logger.info(
            "[trace_id=%s] Plan persisted: session_id=%s version=%s source=%s degraded=%s strategy=%s",
            trace_id,
            session["id"],
            version,
            metadata.get("source", "unknown"),
            metadata.get("degraded", False),
            (regeneration_feedback or {}).get("regeneration_strategy", "-"),
        )
        return build_plan_preview(
            session_id=session["id"],
            plan_record=plan_record,
            configuration=configuration,
            status=SessionState.PLAN_READY.value,
        )

    def _get_planning_session(self, user_id: int, session_id: str, *, trace_id: str) -> dict[str, Any]:
        session = self.store.get_planning_session(user_id, session_id)
        if not session:
            raise_app_error(404, ErrorCode.SESSION_NOT_FOUND, "面试会话不存在", trace_id=trace_id)
        return session

    @staticmethod
    def _resolve_active_plan(session: dict[str, Any], plan_records: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not plan_records:
            return None
        confirmed_plan_id = session.get("confirmed_plan_id")
        if confirmed_plan_id:
            for record in plan_records:
                if record["id"] == confirmed_plan_id:
                    return record
        return plan_records[-1]

    @staticmethod
    def _build_session_title(configuration: dict[str, Any]) -> str:
        """v1.1: 标题按 interview_language 选 label + 后缀。"""
        lang = configuration.get("interview_language") or "en"
        labels = configuration_labels(configuration, locale=lang)
        role = labels.get("target_role_label") or configuration.get("target_role", "")
        return f"{role} {'面试' if lang == 'zh' else 'Interview'}"
