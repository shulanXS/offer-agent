"""V2 动态面试会话 API 响应模型。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas import ChatMessage


class InterviewTopicProgress(BaseModel):
    current_topic_id: str
    current_topic_name: str
    completed_topic_count: int
    total_topic_count: int
    answer_round: int
    max_answer_rounds: int = 12
    phase: Literal["topic_question", "topic_follow_up"] = "topic_question"
    deadline_at: str = ""
    remaining_seconds: int | None = None
    is_wrap_up_zone: bool = False


class LiveInterviewSessionDetail(BaseModel):
    id: str
    title: str
    target_role: str
    status: Literal["plan_confirmed", "active", "evaluating", "completed"]
    configuration: dict[str, Any]
    confirmed_plan_id: str | None = None
    topics_preview: list[dict[str, Any]] = Field(default_factory=list)
    messages: list[ChatMessage]
    progress: InterviewTopicProgress | None = None
    created_at: datetime
    updated_at: datetime
