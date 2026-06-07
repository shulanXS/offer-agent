import { requestJson } from './client'
import type { InterviewSessionListItem } from '@/types/interviewSessionList'

export function listInterviewSessions(token: string) {
  return requestJson<InterviewSessionListItem[]>('/api/interviews', {}, token)
}
