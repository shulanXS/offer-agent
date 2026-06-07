import { listInterviewSessions } from '@/services/interviewSessionList'
import { useQuery } from '@tanstack/react-query'

export const interviewSessionListKeys = {
  all: ['interview-session-list'] as const,
}

const LIST_POLL_INTERVAL_MS = 10_000

export function useInterviewSessionList(token: string, enabled = true) {
  return useQuery({
    queryKey: interviewSessionListKeys.all,
    queryFn: () => listInterviewSessions(token),
    enabled: Boolean(token && enabled),
    refetchInterval: LIST_POLL_INTERVAL_MS,
    refetchOnWindowFocus: true,
  })
}
