from typing import Literal

from pydantic import BaseModel


InterviewListDisplayLabel = Literal["not_started", "in_progress", "evaluating", "pending_evaluation", "completed"]


class InterviewSessionListItem(BaseModel):
    id: str
    title: str
    target_role: str
    target_role_label: str
    target_level: str = ""
    target_level_label: str = ""
    duration_minutes: int = 45
    overall_score: int | None = None
    scored_topic_count: int | None = None
    total_topic_count: int | None = None
    status: str
    display_label: InterviewListDisplayLabel
    action_label: str
    action_path: str
    remaining_seconds: int | None = None
    has_evaluation: bool = False
    session_at: str
    updated_at: str
    created_at: str
