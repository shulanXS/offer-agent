export type InterviewListDisplayLabel =
  | 'not_started'
  | 'in_progress'
  | 'evaluating'
  | 'pending_evaluation'
  | 'completed'

export type InterviewTargetLevel = 'beginner' | 'intermediate' | 'challenge' | string

export interface InterviewSessionListItem {
  id: string
  title: string
  target_role: string
  target_role_label: string
  target_level: InterviewTargetLevel
  target_level_label: string
  duration_minutes: number
  overall_score: number | null
  scored_topic_count: number | null
  total_topic_count: number | null
  status: string
  display_label: InterviewListDisplayLabel
  action_label: string
  action_path: string
  remaining_seconds: number | null
  has_evaluation: boolean
  session_at: string
  updated_at: string
  created_at: string
}

// 注：v1.1 起展示用 i18n（records.status_* / records.level_*），
// 这里不再导出硬编码标签常量。
export {}

