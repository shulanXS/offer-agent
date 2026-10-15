import i18n from '@/i18n'
import { bcp47ForIntl } from '@/i18n/useLocale'
import type { ResumeExtractResponse, ResumeSummary } from '@/types'

export type ResumeCardItem = ResumeSummary & {
  parse_status: 'ready' | 'processing'
}

export const MAX_RESUME_COUNT = 3

export function toResumeCardItem(resume: ResumeSummary): ResumeCardItem {
  return { ...resume, parse_status: 'ready' }
}

export function toResumeSummary(result: ResumeExtractResponse): ResumeSummary {
  return {
    id: result.id ?? '',
    filename: result.filename,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    personal_info: result.personal_info,
    highlights: result.highlights,
    technical_skills: result.technical_skills,
    resume_text: result.resume_text,
    work_experience: result.work_experience,
    project_experience: result.project_experience,
    model_provider: result.model_provider,
    model_name: result.model_name,
  }
}

export function replaceResume(items: ResumeCardItem[], resume: ResumeSummary): ResumeCardItem[] {
  return [toResumeCardItem(resume), ...items.filter((item) => item.id !== resume.id)].sort((a, b) =>
    b.updated_at.localeCompare(a.updated_at),
  )
}

export function createProcessingResume(filename: string): ResumeCardItem {
  const now = new Date().toISOString()
  return {
    id: `temp-${Date.now()}`,
    filename,
    created_at: now,
    updated_at: now,
    personal_info: '',
    highlights: [],
    technical_skills: [],
    resume_text: '',
    work_experience: [],
    project_experience: [],
    model_provider: '',
    model_name: '',
    parse_status: 'processing',
  }
}

export function getResumeBadge(filename: string) {
  const extension = filename.split('.').pop()?.trim().toUpperCase()
  if (!extension || extension === filename.toUpperCase()) {
    return 'CV'
  }
  return extension.slice(0, 4)
}

function currentLocale(): 'en' | 'zh' {
  const raw = (i18n.language || 'en').split('-')[0]
  return (raw === 'zh' ? 'zh' : 'en') as 'en' | 'zh'
}

export function formatResumeMeta(resume: ResumeSummary) {
  const updatedAtText = formatDateTime(resume.updated_at)
  return i18n.t('resumes:updated_at', { time: updatedAtText })
}

export function formatDateTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value || '—'
  }
  return date.toLocaleString(bcp47ForIntl(currentLocale()), {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
