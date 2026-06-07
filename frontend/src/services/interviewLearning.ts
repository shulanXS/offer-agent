import { requestJson } from './client'
import type { LearningContextResponse, LearningRecommendationsResponse } from '@/types/interviewLearning'

export function getLearningRecommendations(
  token: string,
  params: { resume_id: string; target_role: string; interview_type: string },
) {
  const search = new URLSearchParams(params)
  return requestJson<LearningRecommendationsResponse>(
    `/api/users/me/learning-recommendations?${search.toString()}`,
    {},
    token,
  )
}

export function getInterviewLearningContext(token: string, sessionId: string) {
  return requestJson<LearningContextResponse>(`/api/interviews/${sessionId}/learning-context`, {}, token)
}
