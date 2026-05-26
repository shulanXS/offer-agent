import type {
  AuthResponse,
  InterviewSessionDetail,
  ResumeExtractResponse,
  ResumeSummary,
  SessionSummary,
  StreamEvent,
  UserProfile,
} from './types'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

type JsonBody = Record<string, unknown>
type ApiErrorPayload = {
  code?: string
  message?: string
  trace_id?: string
  details?: unknown
  detail?: unknown
}

async function requestJson<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
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
}

async function safeJson(response: Response): Promise<Record<string, unknown> | null> {
  try {
    return (await response.json()) as Record<string, unknown>
  } catch {
    return null
  }
}

export function register(username: string, password: string) {
  return requestJson<AuthResponse>('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

export function login(username: string, password: string) {
  return requestJson<AuthResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

export function getMe(token: string) {
  return requestJson<UserProfile>('/api/auth/me', {}, token)
}

export function listSessions(token: string) {
  return requestJson<SessionSummary[]>('/api/interviews', {}, token)
}

export function getSession(token: string, sessionId: string) {
  return requestJson<InterviewSessionDetail>(`/api/interviews/${sessionId}`, {}, token)
}

export function listResumes(token: string) {
  return requestJson<ResumeSummary[]>('/api/resumes', {}, token)
}

export function getResume(token: string, resumeId: string) {
  return requestJson<ResumeSummary>(`/api/resumes/${resumeId}`, {}, token)
}

export function deleteResume(token: string, resumeId: string) {
  return requestJson<{ ok: boolean }>(`/api/resumes/${resumeId}`, { method: 'DELETE' }, token)
}

export async function extractResume(token: string, file: File): Promise<ResumeExtractResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${API_BASE}/api/resumes/extract`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  })

  if (!response.ok) {
    const payload = await safeJson(response)
    throw new Error(readApiErrorMessage(payload) ?? '简历解析失败')
  }

  return (await response.json()) as ResumeExtractResponse
}

async function consumeEventStream(response: Response, onEvent: (event: StreamEvent) => void): Promise<void> {
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

export async function startInterviewStream(
  token: string,
  body: JsonBody,
  onEvent: (event: StreamEvent) => void,
) {
  const response = await fetch(`${API_BASE}/api/interviews/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  })
  await consumeEventStream(response, onEvent)
}

export async function replyInterviewStream(
  token: string,
  sessionId: string,
  content: string,
  onEvent: (event: StreamEvent) => void,
) {
  const response = await fetch(`${API_BASE}/api/interviews/${sessionId}/reply/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ content }),
  })
  await consumeEventStream(response, onEvent)
}

export function finishInterview(token: string, sessionId: string) {
  return requestJson<InterviewSessionDetail>(`/api/interviews/${sessionId}/finish`, { method: 'POST' }, token)
}

export function activateInterview(token: string, sessionId: string) {
  return requestJson<InterviewSessionDetail>(`/api/interviews/${sessionId}/activate`, { method: 'POST' }, token)
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
