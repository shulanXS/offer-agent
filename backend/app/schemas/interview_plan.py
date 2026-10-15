from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# v1.1: 面试语言，与 UI 语言解耦
InterviewLanguage = Literal["en", "zh"]
DEFAULT_INTERVIEW_LANGUAGE: InterviewLanguage = "en"

# v2.2: 支持的时长档位
ALLOWED_DURATIONS = (15, 30, 45, 60)


class CreateInterviewRequest(BaseModel):
    resume_id: str = Field(min_length=1, max_length=64)
    interview_type: str = Field(min_length=1, max_length=32)
    target_role: str = Field(min_length=1, max_length=64)  # v2.2: 自定义 role 较长
    language: str = Field(default="", max_length=32)  # v2.2: 兼容字段，不再必需
    target_level: str = Field(min_length=1, max_length=32)
    duration_minutes: int = Field(default=45)
    focus_topics: list[str] = Field(default_factory=list, max_length=8)
    jd_text: str = Field(default="", max_length=8000)
    interview_language: InterviewLanguage = DEFAULT_INTERVIEW_LANGUAGE
    # v2.2: 启用算法轮次（手写代码 + AI 判题）
    include_algorithm: bool = False
    # v2.2: 自定义 target role（前端 target_role=__custom__ 时填）
    custom_target_role: str | None = Field(default=None, max_length=64)

    @field_validator("duration_minutes")
    @classmethod
    def _validate_duration(cls, v: int) -> int:
        if v not in ALLOWED_DURATIONS:
            raise ValueError(f"duration_minutes must be one of {ALLOWED_DURATIONS}")
        return v


class PlanTopicPreview(BaseModel):
    id: str
    name: str
    required: bool
    estimated_minutes: int


class CandidateSummaryPreview(BaseModel):
    interview_type: str
    interview_type_label: str
    target_role: str
    target_role_label: str
    language: str
    language_label: str
    target_level: str
    target_level_label: str
    duration_minutes: int
    focus_topics: list[str]
    reference_summary: list[str]
    has_jd: bool


class PlanGenerationMeta(BaseModel):
    source: str
    generation_attempts: int
    degraded: bool
    degraded_reason: str | None = None


class InterviewPlanPreviewResponse(BaseModel):
    session_id: str
    status: Literal["planning", "plan_ready", "plan_confirmed"]
    plan_id: str
    plan_version: int
    candidate_summary: CandidateSummaryPreview
    topics_preview: list[PlanTopicPreview]
    regenerations_remaining: int
    generation_meta: PlanGenerationMeta | None = None
    # v1.1 F4: filled when LLM failed and returned a retryable error
    retryable_error: dict[str, Any] | None = None


class RegeneratePlanRequest(BaseModel):
    regeneration_strategy: str = Field(min_length=1, max_length=64)
    additional_instruction: str = Field(default="", max_length=200)


class PlanVersionHistoryItem(BaseModel):
    plan_id: str
    plan_version: int
    created_at: str
    regeneration_strategy: str | None = None
    topics_preview: list[PlanTopicPreview]
    reference_summary: list[str]


class InterviewPlanSessionDetail(BaseModel):
    id: str
    status: Literal["planning", "plan_ready", "plan_confirmed", "preparing", "active", "completed"]
    configuration: dict[str, Any]
    plan: InterviewPlanPreviewResponse | None = None
    version_history: list[PlanVersionHistoryItem] = Field(default_factory=list)
    confirmed_plan_id: str | None = None
    created_at: str
    updated_at: str
