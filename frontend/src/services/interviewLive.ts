import type { ChatMessage, StreamEvent } from '@/types'
import { consumeEventStream, LLM_SLOW_REQUEST_TIMEOUT_MS, requestJson, withApiBase } from './client'
import type { LiveInterviewProgress, LiveInterviewSessionDetail } from '@/types/interviewLive'

export function getLiveInterviewSession(token: string, sessionId: string) {
  return requestJson<LiveInterviewSessionDetail>(`/api/interviews/${sessionId}`, {}, token)
}

export function activateLiveInterview(token: string, sessionId: string) {
  return requestJson<LiveInterviewSessionDetail>(
    `/api/interviews/${sessionId}/activate`,
    { method: 'POST' },
    token,
    LLM_SLOW_REQUEST_TIMEOUT_MS,
  )
}

export function finishLiveInterview(token: string, sessionId: string) {
  return requestJson<LiveInterviewSessionDetail>(
    `/api/interviews/${sessionId}/finish`,
    { method: 'POST' },
    token,
  )
}

export async function replyLiveInterviewStream(
  token: string,
  sessionId: string,
  content: string,
  onEvent: (event: StreamEvent) => void,
) {
  const response = await fetch(withApiBase(`/api/interviews/${sessionId}/reply/stream`), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ content }),
  })
  await consumeEventStream(response, onEvent)
}

export type { LiveInterviewProgress, LiveInterviewSessionDetail, ChatMessage }
