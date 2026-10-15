from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.rate_limit import limiter, UPLOAD_LIMIT
from app.schemas import ResumeExtractResponse, ResumeSummary
from app.services.resume_service import ResumeService


router = APIRouter(prefix="/resumes", tags=["resumes"])
resume_service = ResumeService()


@router.get("", response_model=list[ResumeSummary])
def list_resumes(current_user: dict = Depends(get_current_user)) -> list[dict]:
    return resume_service.list_resumes(current_user["id"])


@router.get("/{resume_id}", response_model=ResumeSummary)
def get_resume(resume_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    return resume_service.get_resume(current_user["id"], resume_id)


@router.delete("/{resume_id}")
def delete_resume(resume_id: str, current_user: dict = Depends(get_current_user)) -> dict[str, bool]:
    resume_service.delete_resume(current_user["id"], resume_id)
    return {"ok": True}


@router.post("/extract", response_model=ResumeExtractResponse)
@limiter.limit(UPLOAD_LIMIT)
async def extract_resume(
    request: Request,
    file: UploadFile = File(...),
    model_provider: str = Form(settings.llm_provider),
    model_name: str = Form(settings.llm_model),
    current_user: dict = Depends(get_current_user),
) -> dict:
    return await resume_service.parse_upload(
        user_id=current_user["id"], file=file, model_provider=model_provider, model_name=model_name
    )
