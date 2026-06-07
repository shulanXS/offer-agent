from pydantic import BaseModel, Field


class RepeatWeakSignal(BaseModel):
    signal: str
    topic_dimension: str = ""
    count: int = 0
    last_session_id: str = ""
    suggested_focus_topic: str = ""


class ImprovedSignal(BaseModel):
    topic_dimension: str = ""
    topic_name: str = ""
    signals: list[str] = Field(default_factory=list)
    status_label: str = "本轮已覆盖"


class PracticeCrossSessionHint(BaseModel):
    topic_id: str
    signal: str
    repeat_count: int
    hint: str


class SessionComparisonPoint(BaseModel):
    category: str
    tone: str
    headline: str
    detail: str = ""


class SessionComparisonCoverage(BaseModel):
    label: str = "已考察方向"
    baseline_count: int = 0
    current_count: int = 0


class SessionComparison(BaseModel):
    baseline_label: str = "上一场"
    baseline_session_id: str = ""
    baseline_completed_at: str = ""
    discussed_coverage: SessionComparisonCoverage | None = None
    points: list[SessionComparisonPoint] = Field(default_factory=list)
    summary_line: str = ""


class LearningRecommendationsResponse(BaseModel):
    has_learning_profile: bool = False
    recommendations_available: bool = False
    session_count: int = 0
    repeat_weak_signals: list[RepeatWeakSignal] = Field(default_factory=list)
    improved_signals: list[ImprovedSignal] = Field(default_factory=list)
    planning_hints: str = ""


class LearningContextResponse(BaseModel):
    has_learning_profile: bool = False
    session_count: int = 0
    target_role: str = ""
    target_role_label: str = ""
    interview_type: str = ""
    interview_type_label: str = ""
    repeat_weak_signals: list[RepeatWeakSignal] = Field(default_factory=list)
    improved_signals: list[ImprovedSignal] = Field(default_factory=list)
    session_comparison: SessionComparison | None = None
    cross_session_available: bool = False
    practice_cross_session_hints: list[PracticeCrossSessionHint] = Field(default_factory=list)
    repeat_weak_threshold: int = 2
