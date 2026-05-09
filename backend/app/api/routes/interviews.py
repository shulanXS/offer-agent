from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user
from app.schemas import InterviewSessionDetail, ReplyInterviewRequest, SessionSummary, StartInterviewRequest
from app.services.interview_service import InterviewService


router = APIRouter(prefix="/interviews", tags=["interviews"])
service = InterviewService()


@router.get("", response_model=list[SessionSummary])
def list_interviews(current_user: dict = Depends(get_current_user)) -> list[dict]:
    return service.list_sessions(current_user["id"])


@router.get("/{session_id}", response_model=InterviewSessionDetail)
def get_interview(session_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    return service.get_session_detail(current_user["id"], session_id)


@router.get("/{session_id}/evaluation")
def get_evaluation(session_id: str, current_user: dict = Depends(get_current_user)) -> dict | None:
    return service.get_evaluation(current_user["id"], session_id)


@router.post("/{session_id}/finish", response_model=InterviewSessionDetail)
def finish_interview(session_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    return service.finish_interview(current_user["id"], session_id)


@router.post("/{session_id}/activate", response_model=InterviewSessionDetail)
def activate_interview(session_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    return service.activate_interview(current_user["id"], session_id)


@router.post("/stream")
async def start_interview_stream(
    request: StartInterviewRequest, current_user: dict = Depends(get_current_user)
) -> StreamingResponse:
    result = service.start_interview(current_user["id"], request.model_dump())
    return StreamingResponse(service.stream_created_session(result), media_type="text/event-stream")


@router.post("/{session_id}/reply/stream")
async def reply_interview_stream(
    session_id: str, request: ReplyInterviewRequest, current_user: dict = Depends(get_current_user)
) -> StreamingResponse:
    result = service.reply_to_interview(current_user["id"], session_id, request.content)
    return StreamingResponse(service.stream_reply_result(result), media_type="text/event-stream")
