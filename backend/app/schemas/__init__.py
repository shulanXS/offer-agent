from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=24)
    password: str = Field(min_length=6, max_length=64)

    @field_validator("username", "password")
    @classmethod
    def _no_blank(cls, v: str) -> str:
        if not (v or "").strip():
            raise ValueError("must not be blank")
        return v


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=24)
    password: str = Field(min_length=6, max_length=64)

    @field_validator("username", "password")
    @classmethod
    def _no_blank(cls, v: str) -> str:
        if not (v or "").strip():
            raise ValueError("must not be blank")
        return v


class UserProfile(BaseModel):
    id: int
    username: str
    quota_remaining: int
    tier: str = "free"
    subscription_expires_at: str | None = None


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
    duration_minutes_options: list[int] = Field(default_factory=list)
    include_algorithm_supported: bool = False
    max_focus_topics: int
    focus_topics_recommended: list[InterviewOption] = Field(default_factory=list)


