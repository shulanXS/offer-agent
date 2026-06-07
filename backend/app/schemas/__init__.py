from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=24)
    password: str = Field(min_length=6, max_length=64)


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=24)
    password: str = Field(min_length=6, max_length=64)


class UserProfile(BaseModel):
    id: int
    username: str
    quota_remaining: int


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile


class ReplyInterviewRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class ChatMessage(BaseModel):
    id: str
    session_id: str
    seq: int
    role: Literal["assistant", "user", "system"]
    kind: str
    content: str
    created_at: datetime
    meta: dict[str, Any] = Field(default_factory=dict)


class ResumeExtractResponse(BaseModel):
    id: str | None = None
    filename: str
    resume_text: str
    personal_info: str
    highlights: list[str]
    technical_skills: list[str]
    work_experience: list[dict[str, str]]
    project_experience: list[dict[str, str]]
    model_provider: str
    model_name: str


class ResumeSummary(BaseModel):
    id: str
    filename: str
    created_at: datetime
    updated_at: datetime
    personal_info: str
    highlights: list[str]
    technical_skills: list[str]
    resume_text: str
    work_experience: list[dict[str, str]]
    project_experience: list[dict[str, str]]
    model_provider: str
    model_name: str


class InterviewOption(BaseModel):
    value: str
    label: str


class InterviewOptionsResponse(BaseModel):
    interview_types: list[InterviewOption]
    target_roles: list[InterviewOption]
    languages: list[InterviewOption]
    target_levels: list[InterviewOption]
    duration_minutes: int
    max_focus_topics: int


