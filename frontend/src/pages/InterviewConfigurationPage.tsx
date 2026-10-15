import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { InterviewHeaderArt } from '@/components/InterviewHeaderArt'
import { LoadingOverlay } from '@/components/LoadingOverlay'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { SlidersHorizontal } from 'lucide-react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useInterviewOptions } from '@/hooks/useInterviewConfiguration'
import { useCreateInterview } from '@/hooks/useInterviewPlan'
import type { InterviewOption, ResumeSummary } from '@/types'
import type { ResumeCardItem } from '@/utils/resume'
import i18n from '@/i18n'

const DEFAULT_MAX_FOCUS_TOPICS = 6
const baseFocusTopics = ['项目深挖', '技术基础', '系统设计', '业务理解', '问题排查', '沟通表达']
const campusFocusTopics = ['学习能力', '算法与编码']
const agentFocusTopics = ['Agent 工程能力', 'Prompt 设计']

type PracticePrefillState = {
  prefilledFocusTopics?: string[]
}

interface InterviewConfigurationPageProps {
  token: string
  resumes: ResumeCardItem[]
  selectedResume: ResumeSummary | null
}

export function InterviewConfigurationPage({ token, resumes, selectedResume }: InterviewConfigurationPageProps) {
  const { t } = useTranslation('interview')
  const { t: tc } = useTranslation('common')
  const navigate = useNavigate()
  const location = useLocation()
  const prefillAppliedRef = useRef(false)
  const readyResumes = resumes.filter((resume) => resume.parse_status === 'ready')
  const initialResumeId = selectedResume?.id ?? readyResumes[0]?.id ?? ''
  const [resumeId, setResumeId] = useState(initialResumeId)
  const [interviewType, setInterviewType] = useState('experienced')
  const [targetRole, setTargetRole] = useState('backend')
  const [language, setLanguage] = useState('java')
  const [targetLevel, setTargetLevel] = useState('intermediate')
  // v1.1: 面试语言独立配置（默认跟随当前 UI 语言，可独立切换）
  const [interviewLanguage, setInterviewLanguage] = useState<'en' | 'zh'>(
    (i18n.language || 'en').startsWith('zh') ? 'zh' : 'en',
  )
  const [selectedFocusTopics, setSelectedFocusTopics] = useState<string[]>(buildRecommendedFocusTopics('experienced', 'backend'))
  const [jdText, setJdText] = useState('')

  const {
    data: options = null,
    error: optionsLoadError,
    isLoading: isLoadingOptions,
  } = useInterviewOptions(token)
  const createInterviewMutation = useCreateInterview(token)

  const maxFocusTopics = options?.max_focus_topics ?? DEFAULT_MAX_FOCUS_TOPICS
  const optionsError = optionsLoadError ? readError(optionsLoadError) : ''
  const submitError = createInterviewMutation.error ? readError(createInterviewMutation.error) : ''
  const isSubmitting = createInterviewMutation.isPending
  const formDisabled = isLoadingOptions || isSubmitting
  const selectedReadyResume = readyResumes.find((item) => item.id === resumeId) ?? null

  // 国际化的"语言"枚举标签：当前 UI 语言 + i18n
  const localizedInterviewTypes = useMemo(
    () => withLocalizedLabels(options?.interview_types ?? []),
    [options?.interview_types],
  )
  const localizedTargetRoles = useMemo(
    () => withLocalizedLabels(options?.target_roles ?? []),
    [options?.target_roles],
  )
  const localizedLanguages = useMemo(
    () => withLocalizedLabels(options?.languages ?? []),
    [options?.languages],
  )
  const localizedTargetLevels = useMemo(
    () => withLocalizedLabels(options?.target_levels ?? []),
    [options?.target_levels],
  )

  useEffect(() => {
    if (!options) return
    setInterviewType(getInitialValue(options.interview_types, 'experienced'))
    setTargetRole(getInitialValue(options.target_roles, 'backend'))
    setLanguage(getInitialValue(options.languages, 'java'))
    setTargetLevel(getInitialValue(options.target_levels, 'intermediate'))
  }, [options])

  // 监听 i18n 语言变化，同步刷新枚举的展示标签
  const [, setLangTick] = useState(0)
  useEffect(() => {
    const cb = () => setLangTick((v) => v + 1)
    i18n.on('languageChanged', cb)
    return () => {
      i18n.off('languageChanged', cb)
    }
  }, [])

  useEffect(() => {
    if (!resumeId && initialResumeId) {
      setResumeId(initialResumeId)
    }
  }, [initialResumeId, resumeId])

  useEffect(() => {
    if (prefillAppliedRef.current) return
    const state = location.state as PracticePrefillState | null
    const prefilled = state?.prefilledFocusTopics?.filter(Boolean) ?? []
    if (!prefilled.length) return
    prefillAppliedRef.current = true
    setSelectedFocusTopics(prefilled.slice(0, maxFocusTopics))
  }, [location.state, maxFocusTopics])

  const recommendedFocusTopics = useMemo(() => {
    return buildRecommendedFocusTopics(interviewType, targetRole).slice(0, maxFocusTopics)
  }, [interviewType, maxFocusTopics, targetRole])

  function toggleFocusTopic(topic: string) {
    setSelectedFocusTopics((current) => {
      if (current.includes(topic)) {
        return current.filter((item) => item !== topic)
      }
      return [...current, topic].slice(0, maxFocusTopics)
    })
  }

  function handleCreatePlan() {
    if (!selectedReadyResume || selectedFocusTopics.length === 0) {
      return
    }

    createInterviewMutation.mutate(
      {
        resume_id: resumeId,
        interview_type: interviewType,
        target_role: targetRole,
        language,
        target_level: targetLevel,
        duration_minutes: 45,
        focus_topics: selectedFocusTopics,
        jd_text: jdText.trim(),
        interview_language: interviewLanguage,
      },
      {
        onSuccess: (plan) => {
          navigate(`/interviews/${plan.session_id}/plan`)
        },
      },
    )
  }

  return (
    <>
      <header className="v2-page-header">
        <div>
          <div className="v2-title-row">
            <h2>{t('config_title')}</h2>
          </div>
          <p>{t('config_subtitle')}</p>
        </div>
        <InterviewHeaderArt />
      </header>

      <section className="v2-config-layout">
        <Card className="v2-panel v2-config-form">
          <fieldset className="v2-config-form-fieldset" disabled={formDisabled}>
          <div className="v2-section-heading">
            <span className="v2-section-icon">
              <SlidersHorizontal />
            </span>
            <div>
              <h3>{t('section_basics')}</h3>
              <p>{tc('minutes', { count: 45 })}</p>
            </div>
          </div>

          {optionsError ? <p className="v2-error">{optionsError}</p> : null}
          <div className="v2-field-grid">
            <div className="v2-config-field">
              <Label>{t('section_resume')}</Label>
              <Select value={resumeId} onValueChange={setResumeId} disabled={formDisabled}>
                <SelectTrigger className="v2-resume-select">
                  <SelectValue placeholder="—" />
                </SelectTrigger>
                <SelectContent>
                  {readyResumes.map((resume) => (
                    <SelectItem key={resume.id} value={resume.id}>
                      {resume.filename}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <SegmentedControl
              label={t('label_interview_type')}
              options={localizedInterviewTypes}
              value={interviewType}
              disabled={formDisabled}
              onChange={(value) => {
                setInterviewType(value)
                setSelectedFocusTopics(buildRecommendedFocusTopics(value, targetRole))
              }}
            />
            <SegmentedControl
              label={t('label_target_role')}
              options={localizedTargetRoles}
              value={targetRole}
              disabled={formDisabled}
              onChange={(value) => {
                setTargetRole(value)
                setSelectedFocusTopics(buildRecommendedFocusTopics(interviewType, value))
              }}
            />
            <SegmentedControl
              label={t('label_language')}
              options={localizedLanguages}
              value={language}
              disabled={formDisabled}
              onChange={setLanguage}
            />
            <SegmentedControl
              label={t('label_target_level')}
              options={localizedTargetLevels}
              value={targetLevel}
              disabled={formDisabled}
              onChange={setTargetLevel}
            />
            <SegmentedControl
              label={t('label_interview_language')}
              options={[
                { value: 'en', label: 'English' },
                { value: 'zh', label: '中文' },
              ]}
              value={interviewLanguage}
              disabled={formDisabled}
              onChange={(value) => setInterviewLanguage(value as 'en' | 'zh')}
            />
            <p className="v2-config-hint">{t('interview_language_hint')}</p>
          </div>

          <div className="v2-jd-panel">
            <div className="v2-jd-header">
              <div>
                <h3>JD</h3>
                <p>—</p>
              </div>
              <Badge variant="secondary">{jdText.trim() ? 'JD YES' : 'JD NO'}</Badge>
            </div>
            <textarea
              className="v2-jd-textarea"
              value={jdText}
              maxLength={8000}
              disabled={formDisabled}
              placeholder="JD (optional)"
              onChange={(event) => setJdText(event.target.value)}
            />
          </div>

          <div className="v2-focus-panel">
            <div className="v2-focus-header">
              <span>{t('section_focus')}</span>
              <Badge variant="secondary">{selectedFocusTopics.length}/{maxFocusTopics}</Badge>
            </div>
            <div className="v2-focus-options">
              {recommendedFocusTopics.map((topic) => (
                <button
                  key={topic}
                  type="button"
                  className={selectedFocusTopics.includes(topic) ? 'active' : ''}
                  disabled={formDisabled}
                  onClick={() => toggleFocusTopic(topic)}
                >
                  {topic}
                </button>
              ))}
            </div>
          </div>

          {submitError ? <p className="v2-error">{submitError}</p> : null}
          <Button
            className="v2-primary-action"
            type="button"
            disabled={
              formDisabled ||
              !selectedReadyResume ||
              selectedFocusTopics.length === 0 ||
              Boolean(optionsError)
            }
            onClick={handleCreatePlan}
          >
            {isSubmitting ? t('btn_generating') : t('btn_generate')}
          </Button>
          </fieldset>
        </Card>
      </section>

      <LoadingOverlay open={isSubmitting} message={t('btn_generating')} />
    </>
  )
}

interface SegmentedControlProps {
  label: string
  options: InterviewOption[]
  value: string
  disabled?: boolean
  onChange: (value: string) => void
}

function SegmentedControl({ label, options, value, disabled = false, onChange }: SegmentedControlProps) {
  return (
    <div className="v2-segment-field">
      <span>{label}</span>
      <div className="v2-segment-group">
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            className={option.value === value ? 'active' : ''}
            disabled={disabled}
            onClick={() => onChange(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  )
}

function buildRecommendedFocusTopics(interviewType: string, targetRole: string) {
  const topics = [...baseFocusTopics]
  if (interviewType === 'campus') {
    topics.splice(3, 0, ...campusFocusTopics)
  }
  if (targetRole === 'agent') {
    topics.unshift(...agentFocusTopics)
  }
  return Array.from(new Set(topics)).slice(0, DEFAULT_MAX_FOCUS_TOPICS)
}

function getInitialValue(options: InterviewOption[], preferred: string) {
  return options.some((option) => option.value === preferred) ? preferred : options[0]?.value ?? ''
}

const LABEL_I18N_KEY: Record<string, string> = {
  // interview_types
  campus: 'option_interview_type_campus',
  experienced: 'option_interview_type_experienced',
  // target_roles
  frontend: 'option_target_role_frontend',
  backend: 'option_target_role_backend',
  fullstack: 'option_target_role_fullstack',
  agent: 'option_target_role_agent',
  // languages
  java: 'option_language_java',
  python: 'option_language_python',
  go: 'option_language_go',
  javascript: 'option_language_javascript',
  // target_levels
  beginner: 'option_target_level_beginner',
  intermediate: 'option_target_level_intermediate',
  challenge: 'option_target_level_challenge',
}

function withLocalizedLabels(options: InterviewOption[]): InterviewOption[] {
  if (!options.length) return options
  const ns = 'interview'
  return options.map((opt) => {
    const key = LABEL_I18N_KEY[opt.value]
    const localized = key ? i18n.t(`${ns}:${key}`, { defaultValue: '' }) : ''
    return { ...opt, label: localized || opt.label }
  })
}

function readError(error: unknown) {
  if (error instanceof Error) return error.message
  if (error && typeof error === 'object' && 'code' in error) {
    const code = String((error as { code?: string }).code ?? '')
    if (code) {
      const localized = i18n.t(`errors:${code}`, { defaultValue: '' })
      return localized || code
    }
  }
  return i18n.t('common:request_failed')
}
