from typing import Any, Literal

from pydantic import BaseModel, Field


class EvaluationCoverage(BaseModel):
    completed_topic_count: int
    total_topic_count: int
    topics_with_evidence_count: int
    scored_topic_count: int = 0
    discussed_topic_count: int = 0


class EvaluationUnverifiedItem(BaseModel):
    content: str
    topic_id: str | None = None


class EvaluationEvidenceReference(BaseModel):
    quote: str
    question: str = ""
    answer: str = ""
    sequence: int = 0
    matched_signal: str = ""
    polarity: str = "neutral"
    strength: float = 0.0


class EvaluationAnswerRoundEvidence(BaseModel):
    quote: str = ""
    matched_signal: str = ""
    polarity: str = "neutral"
    strength: float = 0.0


class EvaluationAnswerRound(BaseModel):
    sequence: int = 0
    question: str = ""
    answer: str = ""
    evidence_items: list[EvaluationAnswerRoundEvidence] = Field(default_factory=list)


class EvaluationFeedbackItem(BaseModel):
    title: str
    body: str


class EvaluationCandidateReview(BaseModel):
    headline: str = ""
    summary: str = ""
    highlights: list[EvaluationFeedbackItem] = Field(default_factory=list)
    weaknesses: list[EvaluationFeedbackItem] = Field(default_factory=list)
    suggestions: list[EvaluationFeedbackItem] = Field(default_factory=list)
    coverage_note: str = ""
    overall_score_label: str = "综合得分"


class EvaluationCompetency(BaseModel):
    topic_id: str
    name: str
    dimension: str
    status: Literal["verified", "partially_verified", "unverified"]
    score: int | None = None
    confidence: float
    evaluation_comment: str = ""
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    evidence_references: list[EvaluationEvidenceReference] = Field(default_factory=list)
    answer_rounds: list[EvaluationAnswerRound] = Field(default_factory=list)


class EvaluationJdMatchItem(BaseModel):
    requirement: str
    topic_id: str | None = None
    topic_name: str | None = None
    evidence_quotes: list[str] = Field(default_factory=list)
    note: str | None = None


class EvaluationJdMatch(BaseModel):
    has_jd: bool = True
    requirement_count: int
    verified_aligned: list[EvaluationJdMatchItem] = Field(default_factory=list)
    verified_with_risk: list[EvaluationJdMatchItem] = Field(default_factory=list)
    unverified: list[EvaluationJdMatchItem] = Field(default_factory=list)
    summary: str


class EvaluationQuestionReview(BaseModel):
    topic_id: str
    name: str
    dimension: str
    objective: str = ""
    effective_points: list[str] = Field(default_factory=list)
    gaps_and_risks: list[str] = Field(default_factory=list)
    organization_tips: list[str] = Field(default_factory=list)
    practice_points: list[str] = Field(default_factory=list)
    evidence_quotes: list[str] = Field(default_factory=list)


class EvaluationPracticeRecommendation(BaseModel):
    id: str
    title: str
    focus_topic: str
    topic_id: str
    topic_name: str
    priority: Literal["high", "medium"]
    reason: str
    suggested_actions: list[str] = Field(default_factory=list)


class InterviewEvaluationReport(BaseModel):
    version: int
    source: str
    summary: str
    candidate_review: EvaluationCandidateReview
    overall_score: int | None = None
    coverage_rate: float
    overall_confidence: float
    coverage: EvaluationCoverage
    competencies: list[EvaluationCompetency] = Field(default_factory=list)
    jd_match: EvaluationJdMatch | None = None
    question_reviews: list[EvaluationQuestionReview] = Field(default_factory=list)
    practice_recommendations: list[EvaluationPracticeRecommendation] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unverified_items: list[EvaluationUnverifiedItem] = Field(default_factory=list)
    model_info: dict[str, Any] | None = None


class EvaluateInterviewResponse(BaseModel):
    session_id: str
    status: str
    evaluation: InterviewEvaluationReport
