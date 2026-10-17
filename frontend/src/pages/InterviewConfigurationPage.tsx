import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { InterviewHeaderArt } from '@/components/InterviewHeaderArt'
import { LoadingOverlay } from '@/components/LoadingOverlay'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { ChevronDown, ChevronUp, Code2, SlidersHorizontal } from 'lucide-react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useInterviewOptions } from '@/hooks/useInterviewConfiguration'
import { useCreateInterview } from '@/hooks/useInterviewPlan'
import type { InterviewOption, ResumeSummary } from '@/types'
import type { ResumeCardItem } from '@/utils/resume'
import i18n from '@/i18n'

const CUSTOM_ROLE_TOKEN = '__custom__'
const FALLBACK_MAX_FOCUS = 8

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
  const [targetLevel, setTargetLevel] = useState('intermediate')
  // v1.1: 面试语言独立配置（默认跟随当前 UI 语言，可独立切换）
  const [interviewLanguage, setInterviewLanguage] = useState<'en' | 'zh'>(
    (i18n.language || 'en').startsWith('zh') ? 'zh' : 'en',
  )
  const [selectedFocusTopics, setSelectedFocusTopics] = useState<string[]>([])
  const [jdText, setJdText] = useState('')
  // v2.2：新增
  const [durationMinutes, setDurationMinutes] = useState<number>(45)
  const [includeAlgorithm, setIncludeAlgorithm] = useState<boolean>(true)
  const [customTargetRole, setCustomTargetRole] = useState<string>('')
  const [customFocusInput, setCustomFocusInput] = useState<string>('')
  const [advancedOpen, setAdvancedOpen] = useState<boolean>(false)

  const {
    data: options = null,
    error: optionsLoadError,
    isLoading: isLoadingOptions,
  } = useInterviewOptions(token)
  const createInterviewMutation = useCreateInterview(token)

  const maxFocusTopics = options?.max_focus_topics ?? FALLBACK_MAX_FOCUS
  const optionsError = optionsLoadError ? readError(optionsLoadError) : ''
  const submitError = createInterviewMutation.error ? readError(createInterviewMutation.error) : ''
  const isSubmitting = createInterviewMutation.isPending
  const formDisabled = isLoadingOptions || isSubmitting
  const selectedReadyResume = readyResumes.find((item) => item.id === resumeId) ?? null

  const localizedInterviewTypes = useMemo(
    () => withLocalizedLabels(options?.interview_types ?? []),
    [options?.interview_types],
  )
  const localizedTargetRoles = useMemo(
    () => withLocalizedLabels(options?.target_roles ?? []),
    [options?.target_roles],
  )
  const localizedTargetLevels = useMemo(
    () => withLocalizedLabels(options?.target_levels ?? []),
    [options?.target_levels],
  )

  useEffect(() => {
    if (!options) return
    setInterviewType(getInitialValue(options.interview_types, 'experienced'))
    setTargetRole(getInitialValue(options.target_roles, 'backend'))
    setCustomTargetRole('')  // v2.3: 重新加载 options 时清空残留
    setTargetLevel(getInitialValue(options.target_levels, 'intermediate'))
    const durOptions = options.duration_minutes_options ?? []
    if (durOptions.length) {
      setDurationMinutes((prev) => (durOptions.includes(prev) ? prev : options.duration_minutes))
    }
  }, [options])

  // v2.3: target role 切到非 custom 时清空 custom_target_role
  useEffect(() => {
    if (targetRole !== '__custom__') {
      setCustomTargetRole('')
    }
  }, [targetRole])

  // 监听 i18n 语言变化
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

  // 默认推荐 topic：从后端 focus_topics_recommended 拿
  const recommendedFocusTopics = useMemo(() => {
    if (!options?.focus_topics_recommended?.length) return []
    return options.focus_topics_recommended.map((item) => item.value).slice(0, maxFocusTopics)
  }, [options?.focus_topics_recommended, maxFocusTopics])

  // 初次加载 options 后，不默认勾选任何 topic；用户按需勾选
  // 系统自身已按大厂面试逻辑组织全部 topic，只有用户希望针对性提升某方面时才勾选
  const initializedRef = useRef(false)
  useEffect(() => {
    if (initializedRef.current) return
    initializedRef.current = true
  }, [])

  function toggleFocusTopic(topic: string) {
    setSelectedFocusTopics((current) => {
      if (current.includes(topic)) {
        return current.filter((item) => item !== topic)
      }
      return [...current, topic].slice(0, maxFocusTopics)
    })
  }

  function handleAddCustomFocus() {
    const parts = customFocusInput
      .split(/[,，]/)
      .map((s) => s.trim())
      .filter(Boolean)
    if (!parts.length) return
    setSelectedFocusTopics((current) => {
      const merged = [...current]
      for (const part of parts) {
        if (!merged.includes(part) && merged.length < maxFocusTopics) {
          merged.push(part)
        }
      }
      return merged
    })
    setCustomFocusInput('')
  }

  function handleCreatePlan() {
    if (!selectedReadyResume || selectedFocusTopics.length === 0) {
      return
    }
    const isCustom = targetRole === CUSTOM_ROLE_TOKEN
    createInterviewMutation.mutate(
      {
        resume_id: resumeId,
        interview_type: interviewType,
        target_role: targetRole,
        custom_target_role: isCustom ? customTargetRole.trim() : undefined,
        target_level: targetLevel,
        duration_minutes: durationMinutes,
        focus_topics: selectedFocusTopics,
        jd_text: jdText.trim(),
        interview_language: interviewLanguage,
        include_algorithm: includeAlgorithm,
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
      <header className="app-page-header">
        <div>
          <div className="app-title-row">
            <h2>{t('config_title')}</h2>
          </div>
          <p>{t('config_subtitle')}</p>
        </div>
        <InterviewHeaderArt />
      </header>

      <section className="app-config-layout">
        <Card className="app-panel app-config-form">
          <fieldset className="app-config-form-fieldset" disabled={formDisabled}>
            <div className="app-section-heading">
              <span className="app-section-icon">
                <SlidersHorizontal />
              </span>
              <div>
                <h3>{t('section_basics')}</h3>
                <p>{tc('minutes', { count: durationMinutes })}</p>
              </div>
            </div>

            {optionsError ? <p className="app-error">{optionsError}</p> : null}
            <div className="app-field-grid">
              <div className="app-config-field">
                <Label>{t('section_resume')}</Label>
                <Select value={resumeId} onValueChange={setResumeId} disabled={formDisabled}>
                  <SelectTrigger className="app-resume-select">
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
                onChange={setInterviewType}
              />
              <SegmentedControl
                label={t('label_target_role')}
                options={localizedTargetRoles}
                value={targetRole}
                disabled={formDisabled}
                onChange={setTargetRole}
              />
              {targetRole === CUSTOM_ROLE_TOKEN ? (
                <div className="app-config-field">
                  <Label htmlFor="custom-role">{t('label_custom_role')}</Label>
                  <Input
                    id="custom-role"
                    value={customTargetRole}
                    maxLength={32}
                    disabled={formDisabled}
                    placeholder={t('placeholder_custom_role')}
                    onChange={(e) => setCustomTargetRole(e.target.value)}
                  />
                </div>
              ) : null}
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
                  { value: 'en', label: t('interview_language_option_en') },
                  { value: 'zh', label: t('interview_language_option_zh') },
                ]}
                value={interviewLanguage}
                disabled={formDisabled}
                onChange={(value) => setInterviewLanguage(value as 'en' | 'zh')}
              />
              <p className="app-config-hint">{t('interview_language_hint')}</p>
            </div>

            <div className="app-row-2col">
              <div className="app-config-field">
                <Label htmlFor="duration">{t('label_duration')}</Label>
                <Select
                  value={String(durationMinutes)}
                  onValueChange={(v) => setDurationMinutes(Number(v))}
                  disabled={formDisabled}
                >
                  <SelectTrigger id="duration" className="app-resume-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(options?.duration_minutes_options ?? [15, 30, 45, 60]).map((d) => (
                      <SelectItem key={d} value={String(d)}>
                        {tc('minutes', { count: d })}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="app-config-field app-algorithm-toggle">
                <Label>{t('label_algorithm')}</Label>
                <label className="app-toggle">
                  <input
                    type="checkbox"
                    checked={includeAlgorithm}
                    disabled={formDisabled}
                    onChange={(e) => setIncludeAlgorithm(e.target.checked)}
                  />
                  <span>{includeAlgorithm ? t('algo_on') : t('algo_off')}</span>
                </label>
                <p className="app-config-hint">{t('algo_hint')}</p>
              </div>
            </div>

            <div className="app-jd-panel">
              <div className="app-jd-header">
                <div>
                  <h3>JD</h3>
                  <p>—</p>
                </div>
                <Badge variant="secondary">{jdText.trim() ? 'JD YES' : 'JD NO'}</Badge>
              </div>
              <textarea
                className="app-jd-textarea"
                value={jdText}
                maxLength={8000}
                disabled={formDisabled}
                placeholder="JD (optional)"
                onChange={(event) => setJdText(event.target.value)}
              />
            </div>

            <div className="app-focus-panel">
              <div className="app-focus-header">
                <span>{t('section_focus')}</span>
                <Badge variant="secondary">{selectedFocusTopics.length}/{maxFocusTopics}</Badge>
              </div>
              <div className="app-focus-options">
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
                {selectedFocusTopics
                  .filter((t) => !recommendedFocusTopics.includes(t))
                  .map((topic) => (
                    <button
                      key={topic}
                      type="button"
                      className="active app-focus-custom-chip"
                      disabled={formDisabled}
                      onClick={() => toggleFocusTopic(topic)}
                      title={t('focus_custom_chip_hint')}
                    >
                      {topic} <span aria-hidden="true">×</span>
                    </button>
                  ))}
              </div>
            </div>

            <div className="app-advanced-panel">
              <button
                type="button"
                className="app-advanced-toggle"
                onClick={() => setAdvancedOpen((v) => !v)}
                aria-expanded={advancedOpen}
              >
                {advancedOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                {t('advanced_toggle')}
              </button>
              {advancedOpen ? (
                <div className="app-advanced-body">
                  <Label htmlFor="custom-focus">{t('label_custom_focus')}</Label>
                  <div className="app-custom-focus-row">
                    <Input
                      id="custom-focus"
                      value={customFocusInput}
                      maxLength={32}
                      disabled={formDisabled || selectedFocusTopics.length >= maxFocusTopics}
                      placeholder={t('placeholder_custom_focus')}
                      onChange={(e) => setCustomFocusInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault()
                          handleAddCustomFocus()
                        }
                      }}
                    />
                    <Button
                      type="button"
                      variant="outline"
                      disabled={
                        formDisabled ||
                        !customFocusInput.trim() ||
                        selectedFocusTopics.length >= maxFocusTopics
                      }
                      onClick={handleAddCustomFocus}
                    >
                      {t('btn_add')}
                    </Button>
                  </div>
                  <p className="app-config-hint">{t('custom_focus_hint')}</p>
                </div>
              ) : null}
            </div>

            {submitError ? <p className="app-error">{submitError}</p> : null}
            <Button
              className="app-primary-action"
              type="button"
              disabled={
                formDisabled ||
                !selectedReadyResume ||
                selectedFocusTopics.length === 0 ||
                Boolean(optionsError) ||
                (targetRole === CUSTOM_ROLE_TOKEN && !customTargetRole.trim())
              }
              onClick={handleCreatePlan}
            >
              {isSubmitting ? t('btn_generating') : t('btn_generate')}
            </Button>
            {includeAlgorithm ? (
              <p className="app-algo-note">
                <Code2 size={14} aria-hidden="true" /> {t('algo_panel_note')}
              </p>
            ) : null}
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
    <div className="app-segment-field">
      <span>{label}</span>
      <div className="app-segment-group">
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

function getInitialValue(options: InterviewOption[], preferred: string) {
  return options.some((option) => option.value === preferred) ? preferred : options[0]?.value ?? ''
}

const LABEL_I18N_KEY: Record<string, string> = {
  intern: 'option_interview_type_intern',
  campus: 'option_interview_type_campus',
  experienced: 'option_interview_type_experienced',
  frontend: 'option_target_role_frontend',
  backend: 'option_target_role_backend',
  fullstack: 'option_target_role_fullstack',
  agent: 'option_target_role_agent',
  data_ml: 'option_target_role_data_ml',
  mobile: 'option_target_role_mobile',
  qa: 'option_target_role_qa',
  sre: 'option_target_role_sre',
  embedded: 'option_target_role_embedded',
  java: 'option_language_java',
  python: 'option_language_python',
  go: 'option_language_go',
  javascript: 'option_language_javascript',
  beginner: 'option_target_level_beginner',
  intermediate: 'option_target_level_intermediate',
  challenge: 'option_target_level_challenge',
}

function withLocalizedLabels(options: InterviewOption[]): InterviewOption[] {
  if (!options.length) return options
  const ns = 'interview'
  return options.map((opt) => {
    // __custom__ 是占位符，前端硬编码 label
    if (opt.value === CUSTOM_ROLE_TOKEN) {
      return { ...opt, label: i18n.t(`${ns}:option_target_role_custom`, { defaultValue: 'Custom…' }) }
    }
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
