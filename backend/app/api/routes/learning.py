from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.schemas.learning import LearningRecommendationsResponse
from app.services.learning.query import get_learning_recommendations


router = APIRouter(tags=["learning"])


@router.get("/users/me/learning-recommendations", response_model=LearningRecommendationsResponse)
def learning_recommendations(
    resume_id: str = Query(..., min_length=1),
    target_role: str = Query(..., min_length=1),
    interview_type: str = Query(..., min_length=1),
    current_user: dict = Depends(get_current_user),
) -> dict:
    return get_learning_recommendations(
        user_id=current_user["id"],
        resume_id=resume_id,
        target_role=target_role,
        interview_type=interview_type,
    )
