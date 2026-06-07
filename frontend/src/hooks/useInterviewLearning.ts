import { getInterviewLearningContext, getLearningRecommendations } from '@/services/interviewLearning'
import { useQuery } from '@tanstack/react-query'

export const interviewLearningKeys = {
  context: (sessionId: string) => ['interview-learning-context', sessionId] as const,
  recommendations: (resumeId: string, targetRole: string, interviewType: string) =>
    ['learning-recommendations', resumeId, targetRole, interviewType] as const,
}

export function useInterviewLearningContext(token: string, sessionId: string, enabled = true) {
  return useQuery({
    queryKey: interviewLearningKeys.context(sessionId),
    queryFn: () => getInterviewLearningContext(token, sessionId),
    enabled: Boolean(token && sessionId && enabled),
    staleTime: 30_000,
    retry: 1,
  })
}

export function useLearningRecommendations(
  token: string,
  params: { resume_id: string; target_role: string; interview_type: string },
  enabled = true,
) {
  const { resume_id, target_role, interview_type } = params
  return useQuery({
    queryKey: interviewLearningKeys.recommendations(resume_id, target_role, interview_type),
    queryFn: () => getLearningRecommendations(token, params),
    enabled: Boolean(token && resume_id && target_role && interview_type && enabled),
    staleTime: 30_000,
    retry: 1,
  })
}
