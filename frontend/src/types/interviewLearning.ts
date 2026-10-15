export interface LearningRepeatWeakSignal {
  signal: string
  topic_dimension: string
  count: number
  last_session_id: string
  suggested_focus_topic: string
}

export interface LearningImprovedSignal {
  topic_dimension: string
  topic_name: string
  signals: string[]
  status_label: string
}

export interface LearningPracticeCrossSessionHint {
  topic_id: string
  signal: string
  repeat_count: number
  hint: string
}

export type SessionComparisonTone = 'better' | 'worse' | 'same' | 'unavailable'

export interface SessionComparisonPoint {
  category: string
  tone: SessionComparisonTone
  headline: string
  detail?: string
}

export interface SessionComparisonCoverage {
  label: string
  baseline_count: number
  current_count: number
}

export interface SessionComparison {
  baseline_label: string
  baseline_session_id: string
  baseline_completed_at: string
  discussed_coverage: SessionComparisonCoverage | null
  points: SessionComparisonPoint[]
  summary_line: string
}

export interface LearningRecommendationsResponse {
  has_learning_profile: boolean
  recommendations_available: boolean
  session_count: number
  repeat_weak_signals: LearningRepeatWeakSignal[]
  improved_signals: LearningImprovedSignal[]
  planning_hints: string
}

export interface LearningContextResponse {
  has_learning_profile: boolean
  session_count: number
  target_role: string
  target_role_label: string
  interview_type: string
  interview_type_label: string
  repeat_weak_signals: LearningRepeatWeakSignal[]
  improved_signals: LearningImprovedSignal[]
  session_comparison: SessionComparison | null
  cross_session_available: boolean
  practice_cross_session_hints: LearningPracticeCrossSessionHint[]
  repeat_weak_threshold: number
  // 2.4：上一场总分（用于跨场分数对比；null 表示无上一场或上一场无总分）
  previous_overall_score?: number | null
}

export interface UnifiedPracticeCard {
  id: string
  title: string
  focus_topic: string
  summary: string
}
