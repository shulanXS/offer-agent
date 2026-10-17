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
  // v2.3: 重试用新 requestId（避免与上次流半完成的 user_message 复用）
  requestId?: string
  signal?: AbortSignal
  // v1.1: 网络中断时是否重试一次（仅一次；带新 X-Request-Id 由后端按 seq 配对）
  retryOnError?: boolean
}

const RETRY_DELAY_MS = 800

function makeRequestId(): string {
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
  // v2.3: 每次外层调用固定一个 requestId；retry 时换新 id，
  // 让后端 seq 自增而不是复用上一次 user_message。
  const baseRequestId = options.requestId ?? makeRequestId()
  let requestId = baseRequestId
  let attempt = 0
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
      // v2.3: 换新 requestId 后再重试
      requestId = makeRequestId()
      await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS))
    }
  }
  throw lastError instanceof Error ? lastError : new Error('stream failed')
}

export type { LiveInterviewProgress, LiveInterviewSessionDetail, ChatMessage }
