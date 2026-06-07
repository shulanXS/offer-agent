import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { confirmInterviewPlan, createInterview, getInterviewPlanSession, regenerateInterviewPlan } from '@/services/interviewPlan'
import type { InterviewConfigurationDraft } from '@/types/interviewConfiguration'
import type { InterviewPlanSessionDetail, RegeneratePlanRequest } from '@/types/interviewPlan'

export const interviewPlanKeys = {
  session: (sessionId: string) => ['interview-plan-session', sessionId] as const,
}

export function useCreateInterview(token: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: InterviewConfigurationDraft) => createInterview(token, payload),
    onSuccess: (plan) => {
      queryClient.setQueryData<InterviewPlanSessionDetail>(interviewPlanKeys.session(plan.session_id), {
        id: plan.session_id,
        status: plan.status,
        configuration: {},
        plan,
        version_history: [],
        confirmed_plan_id: null,
        created_at: '',
        updated_at: '',
      })
    },
  })
}

export function useInterviewPlanSessionDetail(token: string, sessionId: string) {
  return useQuery({
    queryKey: interviewPlanKeys.session(sessionId),
    queryFn: () => getInterviewPlanSession(token, sessionId),
    enabled: Boolean(token && sessionId),
  })
}

export function useRegenerateInterviewPlan(token: string, sessionId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: RegeneratePlanRequest) => regenerateInterviewPlan(token, sessionId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: interviewPlanKeys.session(sessionId) })
    },
  })
}

export function useConfirmInterviewPlan(token: string, sessionId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => confirmInterviewPlan(token, sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: interviewPlanKeys.session(sessionId) })
    },
  })
}
