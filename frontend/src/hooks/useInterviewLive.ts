import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { activateLiveInterview, finishLiveInterview, getLiveInterviewSession } from '@/services/interviewLive'
import { isLiveInterviewSession, type LiveInterviewSessionDetail } from '@/types/interviewLive'

export const interviewLiveKeys = {
  session: (sessionId: string) => ['interview-live-session', sessionId] as const,
}

export function useLiveInterviewSession(token: string, sessionId: string, enabled = true) {
  return useQuery({
    queryKey: interviewLiveKeys.session(sessionId),
    queryFn: () => getLiveInterviewSession(token, sessionId),
    enabled: Boolean(token && sessionId && enabled),
    refetchOnWindowFocus: true,
    refetchInterval: (query) => {
      const data = query.state.data
      if (data && isLiveInterviewSession(data) && data.progress?.is_reply_processing) {
        return 2000
      }
      if (data && isLiveInterviewSession(data) && data.status === 'active') {
        return 15000
      }
      return false
    },
  })
}

export function useActivateLiveInterview(token: string, sessionId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => activateLiveInterview(token, sessionId),
    onSuccess: (session: LiveInterviewSessionDetail) => {
      queryClient.setQueryData(interviewLiveKeys.session(sessionId), session)
    },
  })
}

export function useFinishLiveInterview(token: string, sessionId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => finishLiveInterview(token, sessionId),
    onSuccess: (session: LiveInterviewSessionDetail) => {
      queryClient.setQueryData(interviewLiveKeys.session(sessionId), session)
    },
  })
}
