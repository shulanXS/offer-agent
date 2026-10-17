export interface PlanTopicPreview {
  id: string
  name: string
  required: boolean
  estimated_minutes: number
}

export interface CandidateSummaryPreview {
  interview_type: string
  interview_type_label: string
  target_role: string
  target_role_label: string
  language: string
  language_label: string
  target_level: string
  target_level_label: string
  duration_minutes: number
  focus_topics: string[]
  reference_summary: string[]
  has_jd: boolean
}

export interface PlanGenerationMeta {
  source: string
  generation_attempts: number
  degraded: boolean
  degraded_reason?: string | null
}

export interface InterviewPlanPreview {
  session_id: string
  status: 'planning' | 'plan_ready' | 'plan_confirmed'
  plan_id: string
  plan_version: number
  candidate_summary: CandidateSummaryPreview
  topics_preview: PlanTopicPreview[]
  regenerations_remaining: number
  generation_meta?: PlanGenerationMeta | null
}

export interface PlanVersionHistoryItem {
  plan_id: string
  plan_version: number
  created_at: string
  regeneration_strategy: string | null
  topics_preview: PlanTopicPreview[]
  reference_summary: string[]
}

export interface InterviewPlanSessionDetail {
  id: string
  status: string
  configuration: InterviewConfigurationSnapshot
  plan: InterviewPlanPreview | null
  version_history: PlanVersionHistoryItem[]
  confirmed_plan_id: string | null
  created_at: string
  updated_at: string
}

export interface InterviewConfigurationSnapshot {
  resume_id?: string
  interview_type?: string
  target_role?: string
  language?: string
  target_level?: string
  duration_minutes?: number
  focus_topics?: string[]
  jd_text?: string
  include_algorithm?: boolean
  custom_target_role?: string
}

export interface RegeneratePlanRequest {
  regeneration_strategy: string
  additional_instruction?: string
}

export const REGENERATION_STRATEGIES = [
  { value: 'align_resume', i18nKey: 'regen_strategy_align_resume' },
  { value: 'align_jd', i18nKey: 'regen_strategy_align_jd', requiresJd: true },
  { value: 'increase_technical_depth', i18nKey: 'regen_strategy_increase_technical_depth' },
  { value: 'increase_fundamentals', i18nKey: 'regen_strategy_increase_fundamentals' },
  { value: 'increase_practical_cases', i18nKey: 'regen_strategy_increase_practical_cases' },
  { value: 'different_plan', i18nKey: 'regen_strategy_different_plan' },
] as const

export type RegenerationStrategy = (typeof REGENERATION_STRATEGIES)[number]['value']
