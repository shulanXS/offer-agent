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

export interface ReplyStreamOptions {
  // v1.1: X-Request-Id 幂等键；同一请求重试时复用同一 id
  requestId?: string
  // v1.1: AbortController，离开页面或切题时取消
  signal?: AbortSignal
  // v1.1: 网络中断时是否重试一次（仅一次；带同 X-Request-Id 由后端幂等去重）
  retryOnError?: boolean
}

const RETRY_DELAY_MS = 800

function makeRequestId(): string {
  // 简易 UUIDv4 兜底
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `req-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

export async function replyLiveInterviewStream(
  token: string,
  sessionId: string,
  content: string,
  onEvent: (event: StreamEvent) => void,
  options: ReplyStreamOptions = {},
) {
  const requestId = options.requestId ?? makeRequestId()
  let attempt = 0
  // 仅做一次重试，避免用户双击
  const maxAttempts = options.retryOnError ? 2 : 1
  let lastError: unknown = null

  while (attempt < maxAttempts) {
    attempt += 1
    try {
      const response = await fetch(withApiBase(`/api/interviews/${sessionId}/reply/stream`), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
          'X-Request-Id': requestId,
        },
        body: JSON.stringify({ content }),
        signal: options.signal,
      })
      await consumeEventStream(response, onEvent)
      return
    } catch (err) {
      lastError = err
      if (!options.retryOnError || attempt >= maxAttempts) {
        throw err
      }
      // 等待后重试
      await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS))
    }
  }
  throw lastError instanceof Error ? lastError : new Error('stream failed')
}

export type { LiveInterviewProgress, LiveInterviewSessionDetail, ChatMessage }
