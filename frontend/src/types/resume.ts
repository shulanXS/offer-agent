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
