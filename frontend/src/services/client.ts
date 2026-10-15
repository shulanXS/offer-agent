import type { StreamEvent } from '@/types'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

/** 同步调用 LLM 的接口通常需 1–2 分钟，与后端 LLM_TIMEOUT_SECONDS=300 对齐 */
export const LLM_SLOW_REQUEST_TIMEOUT_MS = 300_000

const TOKEN_STORAGE_KEY = 'offer-agent-token'

export type JsonBody = Record<string, unknown>
type ApiErrorPayload = {
  code?: string
  message?: string
  trace_id?: string
  details?: unknown
  detail?: unknown
}

type UnauthorizedHandler = () => void

let unauthorizedHandler: UnauthorizedHandler | null = null

/** 由 App 注册：401 时清 token 并跳登录。 */
export function registerUnauthorizedHandler(handler: UnauthorizedHandler): void {
  unauthorizedHandler = handler
}

/** 应用启动时恢复 401 行为（仅测试使用）。 */
export function clearUnauthorizedHandler(): void {
  unauthorizedHandler = null
}

export function getStoredToken(): string {
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY) ?? ''
  } catch {
    return ''
  }
}

export function setStoredToken(token: string): void {
  try {
    if (token) localStorage.setItem(TOKEN_STORAGE_KEY, token)
    else localStorage.removeItem(TOKEN_STORAGE_KEY)
  } catch {
    /* 忽略 localStorage 不可用 */
  }
}

function handleUnauthorized(): void {
  setStoredToken('')
  if (unauthorizedHandler) {
    try {
      unauthorizedHandler()
    } catch (err) {
      console.error('unauthorized handler failed', err)
    }
  }
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

    if (response.status === 401) {
      // C4：401 自动清 token
      handleUnauthorized()
      const payload = await safeJson(response)
      throw new Error(readApiErrorMessage(payload) ?? '登录已失效，请重新登录')
    }

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

  if (response.status === 401) {
    handleUnauthorized()
    const payload = await safeJson(response)
    throw new Error(readApiErrorMessage(payload) ?? '登录已失效，请重新登录')
  }

  if (!response.ok) {
    const payload = await safeJson(response)
    throw new Error(readApiErrorMessage(payload) ?? '请求失败')
  }

  return (await response.json()) as T
}

export async function consumeEventStream(response: Response, onEvent: (event: StreamEvent) => void): Promise<void> {
  if (!response.ok) {
    if (response.status === 401) {
      handleUnauthorized()
    }
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
    // 按 \r\n\r\n 或 \n\n 都可分块；优先 \n\n
    const chunks = buffer.split('\n\n')
    buffer = chunks.pop() ?? ''

    for (const chunk of chunks) {
      const trimmed = chunk.replace(/\r$/, '').trim()
      if (!trimmed || trimmed.startsWith(':')) continue // 注释行/keep-alive
      const lines = trimmed.split('\n')
      let event = 'message'
      const dataLines: string[] = []
      for (const line of lines) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
      }
      const dataText = dataLines.join('\n')
      let data: unknown
      try {
        data = dataText ? JSON.parse(dataText) : {}
      } catch (err) {
        // D2：单事件坏数据不破坏整流
        console.warn('SSE event data parse failed, skipped', err, dataText.slice(0, 120))
        continue
      }
      onEvent({ event, data: data as StreamEvent['data'] })
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
