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
}

export interface EvaluateInterviewResponse {
  session_id: string
  status: 'evaluating' | 'completed'
  evaluation: InterviewEvaluationReport
}

export const EVALUATION_PRACTICE_PRIORITY_LABELS: Record<EvaluationPracticeRecommendation['priority'], string> = {
  high: '优先练习',
  medium: '建议巩固',
}

export const EVALUATION_COMPETENCY_STATUS_LABELS: Record<EvaluationCompetencyStatus, string> = {
  verified: '表现较好',
  partially_verified: '有亮点待加强',
  unverified: '讨论不足',
}

export const EVALUATION_SOURCE_LABELS: Record<string, string> = {
  evidence_rule: '证据驱动评分',
  agent_enriched: 'Agent 增强报告',
  rule_minimal: '规则版最小报告',
}
