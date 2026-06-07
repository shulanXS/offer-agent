import type { InterviewOptions } from '@/types'
import { requestJson } from './client'

export function getInterviewOptions(token: string) {
  return requestJson<InterviewOptions>('/api/interview-options', {}, token)
}
