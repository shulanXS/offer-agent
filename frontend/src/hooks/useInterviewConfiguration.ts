import { useQuery } from '@tanstack/react-query'
import type { InterviewOptions } from '@/types'
import { getInterviewOptions } from '@/services/interviewConfiguration'

export function useInterviewOptions(token: string) {
  return useQuery<InterviewOptions>({
    queryKey: ['interview-options'],
    queryFn: () => getInterviewOptions(token),
    enabled: Boolean(token),
  })
}
