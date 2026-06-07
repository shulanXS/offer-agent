export interface ChatMessage {
  id: string
  session_id: string
  seq: number
  role: 'assistant' | 'user' | 'system'
  kind: string
  content: string
  created_at: string
  meta: Record<string, unknown>
}

export interface StreamEvent {
  event: string
  data: Record<string, unknown>
}
