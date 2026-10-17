import { LLM_SLOW_REQUEST_TIMEOUT_MS, requestJson } from './client'
import type { EvaluateInterviewResponse } from '@/types/interviewEvaluation'

export function evaluateInterview(token: string, sessionId: string) {
  return requestJson<EvaluateInterviewResponse>(
    `/api/interviews/${sessionId}/evaluate`,
    { method: 'POST' },
    token,
    LLM_SLOW_REQUEST_TIMEOUT_MS,
  )
}

export function getInterviewEvaluation(token: string, sessionId: string) {
  return requestJson<EvaluateInterviewResponse | null>(`/api/interviews/${sessionId}/evaluation`, {}, token)
}

export interface InterviewEvent {
  type: 'evaluation_done' | 'ready' | string
  session_id?: string
  status?: string
  trace_id?: string
  [k: string]: unknown
}

/**
 * v2.3: 订阅面试事件流（SSE）。典型用途：等待 evaluation_done。
 * 浏览器 EventSource 不支持自定义 header，因此 token 走 query 参数。
 */
export function subscribeInterviewEvents(
  sessionId: string,
  onEvent: (evt: InterviewEvent) => void,
  onError?: (err: unknown) => void,
  onDone?: () => void,
): EventSource {
  const url = `/api/interviews/${encodeURIComponent(sessionId)}/events/stream?token=${encodeURIComponent(currentToken())}`
  const es = new EventSource(url, { withCredentials: false })
  es.addEventListener('ready', () => {
    onEvent({ type: 'ready' })
  })
  es.addEventListener('evaluation_done', (e: MessageEvent) => {
    try {
      const data = JSON.parse(e.data) as InterviewEvent
      onEvent({ ...data, type: 'evaluation_done' })
    } catch {
      onEvent({ type: 'evaluation_done' })
    }
    onDone?.()
    es.close()
  })
  es.onerror = (err) => {
    onError?.(err)
    // EventSource 默认会自动重连；只关闭一次错误后的实例
  }
  return es
}

function currentToken(): string {
  // 避免引入 hook；sse 调用时 token 已确定
  try {
    return localStorage.getItem('auth_token') || ''
  } catch {
    return ''
  }
}
