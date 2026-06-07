import type { StreamEvent } from '@/types'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

/** 同步调用 LLM 的接口通常需 1–2 分钟，与后端 LLM_TIMEOUT_SECONDS=300 对齐 */
export const LLM_SLOW_REQUEST_TIMEOUT_MS = 300_000

export type JsonBody = Record<string, unknown>
type ApiErrorPayload = {
  code?: string
  message?: string
  trace_id?: string
  details?: unknown
  detail?: unknown
}

export async function requestJson<T>(
  path: string,
  init: RequestInit = {},
  token?: string,
  timeoutMs = 30_000,
): Promise<T> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs)

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init.headers ?? {}),
      },
    })

    if (!response.ok) {
      const payload = await safeJson(response)
      throw new Error(readApiErrorMessage(payload) ?? '请求失败')
    }

    return (await response.json()) as T
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('请求超时，请稍后重试')
    }
    throw error
  } finally {
    window.clearTimeout(timeout)
  }
}

export async function requestFormData<T>(path: string, formData: FormData, token: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  })

  if (!response.ok) {
    const payload = await safeJson(response)
    throw new Error(readApiErrorMessage(payload) ?? '请求失败')
  }

  return (await response.json()) as T
}

export async function consumeEventStream(response: Response, onEvent: (event: StreamEvent) => void): Promise<void> {
  if (!response.ok) {
    const payload = await safeJson(response)
    throw new Error(readApiErrorMessage(payload) ?? '流式请求失败')
  }

  if (!response.body) {
    throw new Error('浏览器不支持当前流式能力')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }
    buffer += decoder.decode(value, { stream: true })
    const chunks = buffer.split('\n\n')
    buffer = chunks.pop() ?? ''

    for (const chunk of chunks) {
      const lines = chunk.split('\n')
      const event = lines.find((line) => line.startsWith('event:'))?.slice(6).trim() ?? 'message'
      const dataLine = lines.find((line) => line.startsWith('data:'))?.slice(5).trim() ?? '{}'
      onEvent({ event, data: JSON.parse(dataLine) })
    }
  }
}

export function withApiBase(path: string) {
  return `${API_BASE}${path}`
}

async function safeJson(response: Response): Promise<Record<string, unknown> | null> {
  try {
    return (await response.json()) as Record<string, unknown>
  } catch {
    return null
  }
}

function readApiErrorMessage(payload: ApiErrorPayload | null): string | null {
  if (!payload) return null

  if (typeof payload.message === 'string' && payload.message.trim()) {
    return appendTraceId(payload.message, payload.trace_id)
  }

  if (typeof payload.detail === 'string') {
    return payload.detail
  }

  const detailObject = isRecord(payload.detail) ? payload.detail : null
  if (detailObject && typeof detailObject.message === 'string' && detailObject.message.trim()) {
    return appendTraceId(detailObject.message, typeof detailObject.trace_id === 'string' ? detailObject.trace_id : undefined)
  }

  const details = payload.details ?? detailObject?.details ?? payload.detail
  if (Array.isArray(details)) {
    const messages = details
      .map((item) => {
        if (!item || typeof item !== 'object') return null
        const entry = item as Record<string, unknown>
        const field = typeof entry.field === 'string' ? entry.field : Array.isArray(entry.loc) ? entry.loc.slice(1).join('.') : '字段'
        const message =
          typeof entry.message === 'string' ? entry.message : typeof entry.msg === 'string' ? entry.msg : '参数校验失败'
        return `${field || '字段'}: ${message}`
      })
      .filter((item): item is string => Boolean(item))
    if (messages.length > 0) {
      return messages.join('；')
    }
  }

  return null
}

function appendTraceId(message: string, traceId?: string) {
  return traceId ? `${message} [${traceId}]` : message
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}
