export interface EvaluationCoverage {
  completed_topic_count: number
  total_topic_count: number
  topics_with_evidence_count: number
  scored_topic_count?: number
  discussed_topic_count?: number
}

export interface EvaluationUnverifiedItem {
  content: string
  topic_id?: string
}

export type EvaluationCompetencyStatus = 'verified' | 'partially_verified' | 'unverified'

export interface EvaluationEvidenceReference {
  quote: string
  question?: string
  answer?: string
  sequence?: number
  matched_signal?: string
  polarity?: string
  strength?: number
}

export interface EvaluationAnswerRoundEvidence {
  quote?: string
  matched_signal?: string
  polarity?: string
  strength?: number
}

export interface EvaluationAnswerRound {
  sequence: number
  question: string
  answer: string
  evidence_items: EvaluationAnswerRoundEvidence[]
}

export interface EvaluationJdMatchItem {
  requirement: string
  topic_id?: string | null
  topic_name?: string | null
  evidence_quotes?: string[]
  note?: string | null
}

export interface EvaluationJdMatch {
  has_jd: boolean
  requirement_count: number
  verified_aligned: EvaluationJdMatchItem[]
  verified_with_risk: EvaluationJdMatchItem[]
  unverified: EvaluationJdMatchItem[]
  summary: string
}

export interface EvaluationQuestionReview {
  topic_id: string
  name: string
  dimension: string
  objective?: string
  effective_points: string[]
  gaps_and_risks: string[]
  organization_tips: string[]
  practice_points: string[]
  evidence_quotes: string[]
}

export interface EvaluationPracticeRecommendation {
  id: string
  title: string
  focus_topic: string
  topic_id: string
  topic_name: string
  topic_ids?: string[]
  topic_names?: string[]
  priority: 'high' | 'medium'
  reason: string
  summary?: string
  suggested_actions: string[]
}

export interface EvaluationFeedbackItem {
  title: string
  body: string
}

export type EvaluationFeedbackEntry = string | EvaluationFeedbackItem

export interface EvaluationCandidateReview {
  headline: string
  summary: string
  highlights?: EvaluationFeedbackEntry[]
  weaknesses: EvaluationFeedbackEntry[]
  suggestions: EvaluationFeedbackEntry[]
  coverage_note?: string
  overall_score_label?: string
}

export interface EvaluationCompetency {
  topic_id: string
  name: string
  dimension: string
  status: EvaluationCompetencyStatus
  score: number | null
  confidence: number
  evaluation_comment?: string
  strengths: string[]
  risks: string[]
  evidence_references: EvaluationEvidenceReference[]
  answer_rounds?: EvaluationAnswerRound[]
}

export interface InterviewEvaluationReport {
  version: number
  source: string
  summary: string
  candidate_review: EvaluationCandidateReview
  overall_score?: number | null
  coverage_rate: number
  overall_confidence: number
  coverage: EvaluationCoverage
  competencies?: EvaluationCompetency[]
  jd_match?: EvaluationJdMatch | null
  question_reviews?: EvaluationQuestionReview[]
  practice_recommendations?: EvaluationPracticeRecommendation[]
  strengths: string[]
  risks: string[]
  unverified_items: EvaluationUnverifiedItem[]
  model_info?: Record<string, unknown> | null
  // B1：降级报告显式标记
  degraded?: boolean
  degraded_reason?: string
  degraded_message?: string
}

export interface EvaluateInterviewResponse {
  session_id: string
  status: 'evaluating' | 'completed'
  evaluation: InterviewEvaluationReport
}

export const EVALUATION_PRACTICE_PRIORITY_I18N_KEYS: Record<EvaluationPracticeRecommendation['priority'], string> = {
  high: 'practice_priority_high',
  medium: 'practice_priority_medium',
}

export const EVALUATION_COMPETENCY_STATUS_I18N_KEYS: Record<EvaluationCompetencyStatus, string> = {
  verified: 'competency_status_verified',
  partially_verified: 'competency_status_partially_verified',
  unverified: 'competency_status_unverified',
}

export const EVALUATION_SOURCE_I18N_KEYS: Record<string, string> = {
  evidence_rule: 'source_evidence_rule',
  agent_enriched: 'source_agent_enriched',
  rule_minimal: 'source_rule_minimal',
}
