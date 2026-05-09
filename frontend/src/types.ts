export type SessionStatus = 'preparing' | 'active' | 'completed'

export interface UserProfile {
  id: number
  username: string
  quota_remaining: number
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: UserProfile
}

export interface SessionSummary {
  id: string
  title: string
  target_role: string
  status: SessionStatus
  created_at: string
  updated_at: string
}

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

export interface InterviewEvaluation {
  overall_score: number
  answered_questions: number
  rating: string
  summary: string
  strengths: string[]
  improvement_suggestions: string[]
}

export interface InterviewQuestionPreview {
  id: string
  title: string
  prompt: string
  focus: string
  follow_up_hint: string
}

export interface InterviewSessionDetail extends SessionSummary {
  profile: {
    resume_id?: string
    job_title: string
    target_role: string
    language?: string
    difficulty_level?: string
    resume_text: string
    highlights: string[]
    personal_info?: string
    technical_skills?: string[]
    work_experience?: { name: string; detail: string }[]
    project_experience?: { name: string; detail: string }[]
    model_provider?: string
    model_name?: string
  }
  planned_questions: InterviewQuestionPreview[]
  messages: ChatMessage[]
  evaluation: InterviewEvaluation | null
}

export interface ResumeExtractResponse {
  id?: string | null
  filename: string
  resume_text: string
  personal_info: string
  highlights: string[]
  technical_skills: string[]
  work_experience: { name: string; detail: string }[]
  project_experience: { name: string; detail: string }[]
  model_provider: string
  model_name: string
}

export interface ResumeSummary {
  id: string
  filename: string
  created_at: string
  updated_at: string
  personal_info: string
  highlights: string[]
  technical_skills: string[]
  resume_text: string
  work_experience: { name: string; detail: string }[]
  project_experience: { name: string; detail: string }[]
  model_provider: string
  model_name: string
}

export interface StreamEvent {
  event: string
  data: Record<string, unknown>
}
