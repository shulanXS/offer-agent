import logging
from typing import Any

from app.agent.workflow import CvInterviewWorkflow
from app.core.config import settings
from app.core.constants import DEFAULT_JOB_TITLE, InterviewSessionStatus
from app.core.errors import ErrorCode, raise_app_error
from app.core.logging_utils import log_payload, new_trace_id
from app.rag.service import PlanningRAGService
from app.core.streaming import format_sse, stream_text
from app.db.store import Store


logger = logging.getLogger("uvicorn.error")


class InterviewService:
    def __init__(self) -> None:
        self.workflow = CvInterviewWorkflow()
        self.store = Store()
        self.planning_rag = PlanningRAGService()

    def list_sessions(self, user_id: int) -> list[dict[str, Any]]:
        return [self._serialize_summary(item) for item in self.store.list_sessions(user_id)]

    def get_session_detail(self, user_id: int, session_id: str) -> dict[str, Any]:
        session = self.store.get_session(user_id, session_id)
        if not session:
            raise_app_error(404, ErrorCode.SESSION_NOT_FOUND, "面试会话不存在")
        return self._serialize_detail(session)

    def get_evaluation(self, user_id: int, session_id: str) -> dict[str, Any] | None:
        session = self.store.get_session(user_id, session_id)
        if not session:
            raise_app_error(404, ErrorCode.SESSION_NOT_FOUND, "面试会话不存在")
        return session.get("evaluation")

    def start_interview(self, user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        trace_id = new_trace_id("interview")
        if len((payload.get("resume_text") or "").strip()) < 20:
            logger.warning("[trace_id=%s] Interview start rejected because resume text is too short: user_id=%s", trace_id, user_id)
            raise_app_error(400, ErrorCode.INTERVIEW_INPUT_INVALID, "请先上传并解析简历，或填写足够的简历摘要", trace_id=trace_id)
        user = self.store.decrement_quota(user_id)
        if not user:
            logger.warning("[trace_id=%s] Interview start rejected because quota is exhausted: user_id=%s", trace_id, user_id)
            raise_app_error(429, ErrorCode.INTERVIEW_QUOTA_EXHAUSTED, "面试额度不足", trace_id=trace_id)
        payload = {
            **payload,
            "trace_id": trace_id,
            "model_provider": (payload.get("model_provider") or settings.llm_provider or "").strip(),
            "model_name": (payload.get("model_name") or settings.llm_model or "").strip(),
        }
        rag_context = self.planning_rag.retrieve_for_planning(
            target_role=str(payload.get("target_role", "")),
            job_title=str(payload.get("job_title", "")),
            language=str(payload.get("language", "")),
            difficulty_level=str(payload.get("difficulty_level", "")),
            technical_skills=[str(item) for item in payload.get("technical_skills", [])],
            highlights=[str(item) for item in payload.get("highlights", [])],
            resume_text=str(payload.get("resume_text", "")),
            trace_id=trace_id,
        )
        payload = {
            **payload,
            "planning_rag_context": rag_context.context,
            "planning_rag_focus_points": rag_context.focus_points,
            "planning_rag_sources": [item.to_log_dict() for item in rag_context.sources],
        }
        logger.info(
            "[trace_id=%s] Interview start requested: provider=%s model=%s resume_id=%s user_id=%s",
            trace_id,
            payload["model_provider"] or "-",
            payload["model_name"] or "-",
            payload.get("resume_id") or "-",
            user_id,
        )
        log_payload(logger, logging.INFO, "Interview start payload", payload, trace_id=trace_id)
        if payload["model_provider"] == "mock":
            logger.warning("[trace_id=%s] Interview start is using mock mode: user_id=%s", trace_id, user_id)

        try:
            bootstrap = self.workflow.bootstrap(payload)
        except ValueError as exc:
            logger.exception("[trace_id=%s] Interview start failed due to model configuration", trace_id)
            raise_app_error(500, ErrorCode.MODEL_CONFIG_INVALID, f"模型配置错误: {exc}", trace_id=trace_id)
        except Exception as exc:
            logger.exception("[trace_id=%s] Interview start failed during bootstrap", trace_id)
            raise_app_error(502, ErrorCode.INTERVIEW_BOOTSTRAP_FAILED, f"面试题生成失败: {exc}", trace_id=trace_id)
        log_payload(logger, logging.INFO, "Interview bootstrap response", bootstrap, trace_id=trace_id)
        session = self.store.create_session(
            user_id=user_id,
            title=bootstrap["title"],
            target_role=payload.get("target_role") or payload.get("job_title") or DEFAULT_JOB_TITLE,
            status=InterviewSessionStatus.PREPARING.value,
            profile=payload,
            workflow_state=bootstrap["workflow_state"],
        )
        assistant_message = self.store.create_message(
            session_id=session["id"],
            role="assistant",
            kind="question",
            content=bootstrap["opening_message"],
        )
        session["messages"] = [assistant_message]
        log_payload(
            logger,
            logging.INFO,
            f"Interview session created: session_id={session['id']}",
            {"session": session, "assistant_message": assistant_message, "user": user},
            trace_id=trace_id,
        )
        return {"session": session, "assistant_message": assistant_message, "user": user}

    def activate_interview(self, user_id: int, session_id: str) -> dict[str, Any]:
        session = self.store.get_session(user_id, session_id)
        if not session:
            raise_app_error(404, ErrorCode.SESSION_NOT_FOUND, "面试会话不存在")
        if session["status"] == InterviewSessionStatus.COMPLETED.value:
            raise_app_error(409, ErrorCode.SESSION_ALREADY_COMPLETED, "当前会话已结束")
        if session["status"] == InterviewSessionStatus.ACTIVE.value:
            return self._serialize_detail(session)
        trace_id = session["workflow_state"].get("trace_id", "") or new_trace_id("interview")
        logger.info("[trace_id=%s] Interview activated: session_id=%s user_id=%s", trace_id, session_id, user_id)
        self.store.update_session(session_id, status=InterviewSessionStatus.ACTIVE.value)
        updated = self.store.get_session(user_id, session_id)
        log_payload(
            logger,
            logging.INFO,
            f"Interview activation result: session_id={session_id}",
            updated,
            trace_id=trace_id,
        )
        return self._serialize_detail(updated or session)

    def reply_to_interview(self, user_id: int, session_id: str, answer: str) -> dict[str, Any]:
        session = self.store.get_session(user_id, session_id)
        if not session:
            raise_app_error(404, ErrorCode.SESSION_NOT_FOUND, "面试会话不存在")
        if session["status"] == InterviewSessionStatus.COMPLETED.value:
            raise_app_error(409, ErrorCode.SESSION_ALREADY_COMPLETED, "当前会话已结束")
        if session["status"] != InterviewSessionStatus.ACTIVE.value:
            raise_app_error(409, ErrorCode.SESSION_NOT_ACTIVE, "请先正式开始面试")
        trace_id = session["workflow_state"].get("trace_id", "") or new_trace_id("interview")
        logger.info(
            "[trace_id=%s] Interview reply requested: session_id=%s provider=%s model=%s user_id=%s",
            trace_id,
            session_id,
            session["workflow_state"].get("model_provider", "") or "-",
            session["workflow_state"].get("model_name", "") or "-",
            user_id,
        )
        log_payload(
            logger,
            logging.INFO,
            f"Interview reply input: session_id={session_id}",
            {"answer": answer, "workflow_state": session["workflow_state"]},
            trace_id=trace_id,
        )
        if session["workflow_state"].get("model_provider", "") == "mock":
            logger.warning("[trace_id=%s] Interview reply is using mock mode: session_id=%s user_id=%s", trace_id, session_id, user_id)

        user_message = self.store.create_message(
            session_id=session_id,
            role="user",
            kind="answer",
            content=answer,
        )
        try:
            result = self.workflow.reply(session["workflow_state"], answer)
        except ValueError as exc:
            logger.exception("[trace_id=%s] Interview reply failed due to model configuration: session_id=%s", trace_id, session_id)
            raise_app_error(500, ErrorCode.MODEL_CONFIG_INVALID, f"模型配置错误: {exc}", trace_id=trace_id)
        except Exception as exc:
            logger.exception("[trace_id=%s] Interview reply failed during workflow execution: session_id=%s", trace_id, session_id)
            raise_app_error(502, ErrorCode.INTERVIEW_REPLY_FAILED, f"面试追问生成失败: {exc}", trace_id=trace_id)
        log_payload(logger, logging.INFO, f"Interview reply workflow output: session_id={session_id}", result, trace_id=trace_id)
        assistant_message = self.store.create_message(
            session_id=session_id,
            role="assistant",
            kind=result["assistant_kind"],
            content=result["assistant_message"],
        )
        self.store.update_session(
            session_id,
            status=result["status"],
            workflow_state=result["workflow_state"],
            evaluation=result.get("evaluation"),
        )
        updated = self.store.get_session(user_id, session_id)
        log_payload(
            logger,
            logging.INFO,
            f"Interview reply persisted result: session_id={session_id}",
            {
                "session": updated,
                "user_message": user_message,
                "assistant_message": assistant_message,
                "evaluation": updated.get("evaluation") if updated else None,
            },
            trace_id=trace_id,
        )
        return {
            "session": updated,
            "user_message": user_message,
            "assistant_message": assistant_message,
            "evaluation": updated.get("evaluation"),
        }

    def finish_interview(self, user_id: int, session_id: str) -> dict[str, Any]:
        session = self.store.get_session(user_id, session_id)
        if not session:
            raise_app_error(404, ErrorCode.SESSION_NOT_FOUND, "面试会话不存在")
        if session["status"] == InterviewSessionStatus.COMPLETED.value:
            return self._serialize_detail(session)
        trace_id = session["workflow_state"].get("trace_id", "") or new_trace_id("interview")
        logger.info(
            "[trace_id=%s] Interview finish requested: session_id=%s provider=%s model=%s user_id=%s",
            trace_id,
            session_id,
            session["workflow_state"].get("model_provider", "") or "-",
            session["workflow_state"].get("model_name", "") or "-",
            user_id,
        )
        log_payload(
            logger,
            logging.INFO,
            f"Interview finish input: session_id={session_id}",
            session["workflow_state"],
            trace_id=trace_id,
        )
        if session["workflow_state"].get("model_provider", "") == "mock":
            logger.warning("[trace_id=%s] Interview finish is using mock mode: session_id=%s user_id=%s", trace_id, session_id, user_id)

        try:
            result = self.workflow.finish(session["workflow_state"])
        except ValueError as exc:
            logger.exception("[trace_id=%s] Interview finish failed due to model configuration: session_id=%s", trace_id, session_id)
            raise_app_error(500, ErrorCode.MODEL_CONFIG_INVALID, f"模型配置错误: {exc}", trace_id=trace_id)
        except Exception as exc:
            logger.exception("[trace_id=%s] Interview finish failed during evaluation: session_id=%s", trace_id, session_id)
            raise_app_error(502, ErrorCode.INTERVIEW_EVALUATION_FAILED, f"面试评估生成失败: {exc}", trace_id=trace_id)
        log_payload(logger, logging.INFO, f"Interview finish workflow output: session_id={session_id}", result, trace_id=trace_id)
        assistant_message = self.store.create_message(
            session_id=session_id,
            role="assistant",
            kind=result["assistant_kind"],
            content=result["assistant_message"],
        )
        self.store.update_session(
            session_id,
            status=result["status"],
            workflow_state=result["workflow_state"],
            evaluation=result["evaluation"],
        )
        updated = self.store.get_session(user_id, session_id)
        log_payload(
            logger,
            logging.INFO,
            f"Interview finish persisted result: session_id={session_id}",
            {"session": updated, "assistant_message": assistant_message},
            trace_id=trace_id,
        )
        return self._serialize_detail(updated or session)

    async def stream_created_session(self, payload: dict[str, Any]) -> Any:
        session = payload["session"]
        assistant_message = payload["assistant_message"]
        user = payload["user"]
        yield format_sse(
            "session",
            {
                "session": self._serialize_summary(session),
                "planned_questions": self._serialize_questions(session),
                "quota_remaining": user["quota_remaining"],
            },
        )
        yield format_sse("message_start", {"session_id": session["id"], "message": assistant_message})
        async for chunk in stream_text(assistant_message["content"]):
            yield format_sse("delta", {"message_id": assistant_message["id"], "delta": chunk})
        yield format_sse("message_end", {"message": assistant_message})
        yield format_sse("done", {"status": session["status"], "session_id": session["id"]})

    async def stream_reply_result(self, payload: dict[str, Any]) -> Any:
        session = payload["session"]
        assistant_message = payload["assistant_message"]
        yield format_sse("message_start", {"session_id": session["id"], "message": assistant_message})
        async for chunk in stream_text(assistant_message["content"]):
            yield format_sse("delta", {"message_id": assistant_message["id"], "delta": chunk})
        yield format_sse("message_end", {"message": assistant_message})
        if payload.get("evaluation"):
            yield format_sse("evaluation", {"evaluation": payload["evaluation"]})
        yield format_sse("done", {"status": session["status"], "session_id": session["id"]})

    @staticmethod
    def _serialize_summary(session: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": session["id"],
            "title": session["title"],
            "target_role": session["target_role"],
            "status": session["status"],
            "created_at": session["created_at"],
            "updated_at": session["updated_at"],
        }

    def _serialize_detail(self, session: dict[str, Any]) -> dict[str, Any]:
        return {
            **self._serialize_summary(session),
            "profile": session["profile"],
            "planned_questions": self._serialize_questions(session),
            "messages": session["messages"],
            "evaluation": session.get("evaluation"),
        }

    @staticmethod
    def _serialize_questions(session: dict[str, Any]) -> list[dict[str, Any]]:
        workflow_state = session.get("workflow_state") or {}
        questions = workflow_state.get("questions") or []
        if not isinstance(questions, list):
            return []
        return [
            {
                "id": str(item.get("id", "")).strip(),
                "title": str(item.get("title", "")).strip(),
                "prompt": str(item.get("prompt", "")).strip(),
                "focus": str(item.get("focus", "")).strip(),
                "follow_up_hint": str(item.get("follow_up_hint", "")).strip(),
            }
            for item in questions
            if isinstance(item, dict) and str(item.get("prompt", "")).strip()
        ]
