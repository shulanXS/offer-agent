import type { ResumeExtractResponse, ResumeSummary } from '@/types'
import { requestFormData, requestJson } from './client'

export function listResumes(token: string) {
  return requestJson<ResumeSummary[]>('/api/resumes', {}, token)
}

export function getResume(token: string, resumeId: string) {
  return requestJson<ResumeSummary>(`/api/resumes/${resumeId}`, {}, token)
}

export function deleteResume(token: string, resumeId: string) {
  return requestJson<{ ok: boolean }>(`/api/resumes/${resumeId}`, { method: 'DELETE' }, token)
}

export function extractResume(token: string, file: File): Promise<ResumeExtractResponse> {
  const formData = new FormData()
  formData.append('file', file)
  return requestFormData<ResumeExtractResponse>('/api/resumes/extract', formData, token)
}
