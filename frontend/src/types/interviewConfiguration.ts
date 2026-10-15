export interface InterviewOption {
  value: string
  label: string
}

export interface InterviewOptions {
  interview_types: InterviewOption[]
  target_roles: InterviewOption[]
  languages: InterviewOption[]
  target_levels: InterviewOption[]
  duration_minutes: number
  duration_minutes_options?: number[]
  include_algorithm_supported?: boolean
  max_focus_topics: number
  focus_topics_recommended?: InterviewOption[]
}

export interface InterviewConfigurationDraft {
  resume_id: string
  interview_type: string
  target_role: string
  language?: string
  custom_target_role?: string
  target_level: string
  duration_minutes: number
  focus_topics: string[]
  jd_text?: string
  interview_language?: 'en' | 'zh'
  include_algorithm?: boolean
}
