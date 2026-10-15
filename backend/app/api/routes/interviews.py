import asyncio

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user
from app.core.errors import ErrorCode, raise_app_error
from app.core.rate_limit import limiter, LLM_LIMIT, UPLOAD_LIMIT
from app.core.streaming import SSE_RESPONSE_HEADERS
from app.schemas import ReplyInterviewRequest
from app.schemas.interview_plan import (
    CreateInterviewRequest,
    InterviewPlanPreviewResponse,
    RegeneratePlanRequest,
)
from app.services.interview_planning_service import InterviewPlanningService
from app.services.interview_agent_service import InterviewAgentService
from app.services.interview_evaluation_service import InterviewEvaluationService
from app.schemas.interview_evaluation import EvaluateInterviewResponse
from app.schemas.interview_session_list import InterviewSessionListItem
from app.schemas.interview_live import LiveInterviewSessionDetail
from app.services.interview_session_list_service import InterviewSessionListService
from app.services.learning.query import get_learning_context_for_session
from app.schemas.learning import LearningContextResponse


router = APIRouter(prefix="/interviews", tags=["interviews"])
planning_service = InterviewPlanningService()
interview_agent_service = InterviewAgentService()
evaluation_service = InterviewEvaluationService()
session_list_service = InterviewSessionListService()


def _require_v2_session(user_id: int, session_id: str) -> None:
    if not interview_agent_service.is_v2_session(user_id, session_id):
        raise_app_error(404, ErrorCode.SESSION_NOT_FOUND, "面试会话不存在")


@router.post("", response_model=InterviewPlanPreviewResponse)
def create_interview(request: CreateInterviewRequest, current_user: dict = Depends(get_current_user)) -> dict:
    return planning_service.create_interview(current_user["id"], request.model_dump())


@router.get("", response_model=list[InterviewSessionListItem])
def list_interviews(current_user: dict = Depends(get_current_user)) -> list[dict]:
    return session_list_service.list_v2_sessions(current_user["id"])


@router.get("/{session_id}")
def get_interview(session_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    live_detail = interview_agent_service.get_live_session_detail(current_user["id"], session_id)
    if live_detail:
        return live_detail
    planning_detail = planning_service.get_session_detail(current_user["id"], session_id)
    if planning_detail:
        return planning_detail
    raise_app_error(404, ErrorCode.SESSION_NOT_FOUND, "面试会话不存在")


@router.post("/{session_id}/plan/generate", response_model=InterviewPlanPreviewResponse)
@limiter.limit(LLM_LIMIT)
def generate_interview_plan(session_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    return planning_service.generate_plan(current_user["id"], session_id)


@router.post("/{session_id}/plan/regenerate", response_model=InterviewPlanPreviewResponse)
@limiter.limit(LLM_LIMIT)
def regenerate_interview_plan(
    session_id: str,
    request: RegeneratePlanRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    return planning_service.regenerate_plan(current_user["id"], session_id, request.model_dump())


@router.post("/{session_id}/plan/confirm", response_model=InterviewPlanPreviewResponse)
def confirm_interview_plan(session_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    return planning_service.confirm_plan(current_user["id"], session_id)


@router.post("/{session_id}/evaluate", response_model=EvaluateInterviewResponse)
@limiter.limit(LLM_LIMIT)
def evaluate_interview(session_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    return evaluation_service.evaluate_interview(current_user["id"], session_id)


@router.get("/{session_id}/evaluation")
def get_evaluation(session_id: str, current_user: dict = Depends(get_current_user)) -> dict | None:
    if evaluation_service.is_v2_evaluable_session(current_user["id"], session_id):
        return evaluation_service.get_evaluation(current_user["id"], session_id)
    return None


@router.get("/{session_id}/learning-context", response_model=LearningContextResponse)
def get_learning_context(session_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    return get_learning_context_for_session(user_id=current_user["id"], session_id=session_id)


@router.post("/{session_id}/finish", response_model=LiveInterviewSessionDetail)
def finish_interview(session_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    _require_v2_session(current_user["id"], session_id)
    return interview_agent_service.finish_interview(current_user["id"], session_id)


@router.post("/{session_id}/activate", response_model=LiveInterviewSessionDetail)
def activate_interview(session_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    _require_v2_session(current_user["id"], session_id)
    return interview_agent_service.activate_interview(current_user["id"], session_id)


@router.post("/{session_id}/reply/stream")
@limiter.limit(LLM_LIMIT)
async def reply_interview_stream(
    session_id: str,
    request: ReplyInterviewRequest,
    current_user: dict = Depends(get_current_user),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
) -> StreamingResponse:
    _require_v2_session(current_user["id"], session_id)
    # A2：X-Request-Id 用作幂等键
    request_id = x_request_id or None
    # A3：默认走真流路径（reply_to_interview_streaming）。
    # 当 client 不支持流式时，service 内部降级到同步。
    payload, delta_queue = await interview_agent_service.reply_to_interview_streaming(
        current_user["id"],
        session_id,
        request.content,
        request_id=request_id,
    )
    payload["delta_queue"] = delta_queue
    return StreamingResponse(
        interview_agent_service.stream_reply_result(payload),
        media_type="text/event-stream",
        headers=SSE_RESPONSE_HEADERS,
    )
