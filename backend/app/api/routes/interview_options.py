from fastapi import APIRouter, Depends

from app.api.deps import get_locale
from app.schemas import InterviewOptionsResponse
from app.services.interview_configuration_service import InterviewConfigurationService


router = APIRouter(prefix="/interview-options", tags=["interview-options"])
configuration_service = InterviewConfigurationService()


@router.get("", response_model=InterviewOptionsResponse)
def get_interview_options(locale: str = Depends(get_locale)) -> dict:
    return configuration_service.get_options(locale=locale)
