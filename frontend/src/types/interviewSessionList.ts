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

export const INTERVIEW_LIST_LABELS: Record<InterviewListDisplayLabel, string> = {
  not_started: '未开始',
  in_progress: '面试中',
  evaluating: '评估中',
  pending_evaluation: '待评估',
  completed: '已结束',
}

export const INTERVIEW_LEVEL_LABELS: Record<string, string> = {
  beginner: '入门',
  intermediate: '进阶',
  challenge: '挑战',
}
