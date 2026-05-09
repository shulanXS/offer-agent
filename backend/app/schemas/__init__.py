from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.constants import DEFAULT_DIFFICULTY_LEVEL, DEFAULT_JOB_TITLE, DEFAULT_LANGUAGE


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


class StartInterviewRequest(BaseModel):
    resume_id: str = ""
    job_title: str = Field(default=DEFAULT_JOB_TITLE, max_length=80)
    target_role: str = Field(default=DEFAULT_JOB_TITLE, max_length=80)
    language: str = Field(default=DEFAULT_LANGUAGE, max_length=40)
    difficulty_level: str = Field(default=DEFAULT_DIFFICULTY_LEVEL, max_length=40)
    resume_text: str = Field(default="", max_length=20000)
    highlights: list[str] = Field(default_factory=list, max_length=8)
    personal_info: str = ""
    work_experience: list[dict[str, str]] = Field(default_factory=list)
    project_experience: list[dict[str, str]] = Field(default_factory=list)
    technical_skills: list[str] = Field(default_factory=list)
    model_provider: str = ""
    model_name: str = ""


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


class SessionSummary(BaseModel):
    id: str
    title: str
    target_role: str
    status: Literal["preparing", "active", "completed"]
    created_at: datetime
    updated_at: datetime


class InterviewEvaluation(BaseModel):
    overall_score: int
    answered_questions: int
    rating: str
    summary: str
    strengths: list[str]
    improvement_suggestions: list[str]


class InterviewQuestionPreview(BaseModel):
    id: str
    title: str
    prompt: str
    focus: str
    follow_up_hint: str


class InterviewSessionDetail(BaseModel):
    id: str
    title: str
    target_role: str
    status: Literal["preparing", "active", "completed"]
    profile: dict[str, Any]
    planned_questions: list[InterviewQuestionPreview] = Field(default_factory=list)
    messages: list[ChatMessage]
    evaluation: InterviewEvaluation | None = None
    created_at: datetime
    updated_at: datetime


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
