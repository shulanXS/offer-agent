import { LLM_SLOW_REQUEST_TIMEOUT_MS, requestJson } from './client'
import type { EvaluateInterviewResponse } from '@/types/interviewEvaluation'

export function evaluateInterview(token: string, sessionId: string) {
  return requestJson<EvaluateInterviewResponse>(
    `/api/interviews/${sessionId}/evaluate`,
    { method: 'POST' },
    token,
    LLM_SLOW_REQUEST_TIMEOUT_MS,
  )
}

export function getInterviewEvaluation(token: string, sessionId: string) {
  return requestJson<EvaluateInterviewResponse | null>(`/api/interviews/${sessionId}/evaluation`, {}, token)
}
