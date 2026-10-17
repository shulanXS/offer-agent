import { LLM_SLOW_REQUEST_TIMEOUT_MS, requestJson } from './client'
import type { InterviewConfigurationDraft } from '@/types/interviewConfiguration'
import type {
  InterviewPlanPreview,
  InterviewPlanSessionDetail,
  RegeneratePlanRequest,
} from '@/types/interviewPlan'

export function createInterview(token: string, payload: InterviewConfigurationDraft) {
  // v2.3: 透传用户选中的 duration_minutes / interview_language；
  // 不再硬编码 45。
  return requestJson<InterviewPlanPreview>(
    '/api/interviews',
    {
      method: 'POST',
      body: JSON.stringify({
        ...payload,
        jd_text: payload.jd_text ?? '',
      }),
    },
    token,
    LLM_SLOW_REQUEST_TIMEOUT_MS,
  )
}

export function getInterviewPlanSession(token: string, sessionId: string) {
  return requestJson<InterviewPlanSessionDetail>(`/api/interviews/${sessionId}`, {}, token)
}

export function generateInterviewPlan(token: string, sessionId: string) {
  return requestJson<InterviewPlanPreview>(
    `/api/interviews/${sessionId}/plan/generate`,
    { method: 'POST' },
    token,
    LLM_SLOW_REQUEST_TIMEOUT_MS,
  )
}

export function regenerateInterviewPlan(token: string, sessionId: string, payload: RegeneratePlanRequest) {
  return requestJson<InterviewPlanPreview>(
    `/api/interviews/${sessionId}/plan/regenerate`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
    token,
    LLM_SLOW_REQUEST_TIMEOUT_MS,
  )
}

export function confirmInterviewPlan(token: string, sessionId: string) {
  return requestJson<InterviewPlanPreview>(`/api/interviews/${sessionId}/plan/confirm`, { method: 'POST' }, token)
}
