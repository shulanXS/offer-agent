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
  max_focus_topics: number
}

export interface InterviewConfigurationDraft {
  resume_id: string
  interview_type: string
  target_role: string
  language: string
  target_level: string
  duration_minutes: number
  focus_topics: string[]
  jd_text?: string
}
