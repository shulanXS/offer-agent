import type { ChatMessage } from './messaging'
import type { PlanTopicPreview } from '@/types/interviewPlan'
import type { InterviewConfigurationSnapshot } from '@/types/interviewPlan'

export interface LiveInterviewProgress {
  current_topic_id: string
  current_topic_name: string
  completed_topic_count: number
  total_topic_count: number
  answer_round: number
  max_answer_rounds: number
  phase: 'topic_question' | 'topic_follow_up'
  deadline_at: string
  remaining_seconds: number | null
  is_wrap_up_zone: boolean
  is_reply_processing?: boolean
}

export interface LiveInterviewSessionDetail {
  id: string
  title: string
  target_role: string
  status: 'plan_confirmed' | 'active' | 'evaluating' | 'completed'
  configuration: InterviewConfigurationSnapshot
  confirmed_plan_id: string | null
  topics_preview: PlanTopicPreview[]
  messages: ChatMessage[]
  progress: LiveInterviewProgress | null
  created_at: string
  updated_at: string
}

export function isLiveInterviewSession(detail: unknown): detail is LiveInterviewSessionDetail {
  if (!detail || typeof detail !== 'object') return false
  const record = detail as Record<string, unknown>
  return Array.isArray(record.messages) && (record.progress === null || typeof record.progress === 'object')
}
