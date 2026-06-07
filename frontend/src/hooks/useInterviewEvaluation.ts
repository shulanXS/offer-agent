import { evaluateInterview, getInterviewEvaluation } from '@/services/interviewEvaluation'
import { getLiveInterviewSession } from '@/services/interviewLive'
import type { EvaluateInterviewResponse } from '@/types/interviewEvaluation'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

export const interviewEvaluationKeys = {
  report: (sessionId: string) => ['interview-evaluation', sessionId] as const,
  session: (sessionId: string) => ['interview-live-session', sessionId] as const,
}

export function useInterviewEvaluationReport(token: string, sessionId: string, enabled = true) {
  return useQuery({
    queryKey: interviewEvaluationKeys.report(sessionId),
    queryFn: async () => {
      // 优先读已落库报告，避免 status 仍为 evaluating 时重复 POST 或长时间等待
      const existing = await getInterviewEvaluation(token, sessionId)
      if (existing?.evaluation) {
        return existing
      }

      const session = await getLiveInterviewSession(token, sessionId)
      if (!session) {
        return null
      }
      if (session.status === 'evaluating') {
        return evaluateInterview(token, sessionId)
      }
      return null
    },
    enabled: Boolean(token && sessionId && enabled),
    retry: 1,
    staleTime: 30_000,
  })
}

export function useRetryInterviewEvaluation(token: string, sessionId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => evaluateInterview(token, sessionId),
    onSuccess: (payload: EvaluateInterviewResponse) => {
      queryClient.setQueryData(interviewEvaluationKeys.report(sessionId), payload)
    },
  })
}
