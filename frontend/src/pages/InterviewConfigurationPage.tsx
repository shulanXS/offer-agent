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
import { useInterviewOptions } from '@/hooks/useInterviewConfiguration'
import { useCreateInterview } from '@/hooks/useInterviewPlan'
import type { InterviewOption, ResumeSummary } from '@/types'
import type { ResumeCardItem } from '@/utils/resume'

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

  useEffect(() => {
    if (!options) return
    setInterviewType(getInitialValue(options.interview_types, 'experienced'))
    setTargetRole(getInitialValue(options.target_roles, 'backend'))
    setLanguage(getInitialValue(options.languages, 'java'))
    setTargetLevel(getInitialValue(options.target_levels, 'intermediate'))
  }, [options])

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
            <h2>创建面试</h2>
          </div>
          <p>选择简历和目标面试信息，可粘贴 JD，也可以不填。</p>
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
              <h3>面试配置</h3>
              <p>本场面试固定 45 分钟，JD 可选。</p>
            </div>
          </div>

          {optionsError ? <p className="v2-error">{optionsError}</p> : null}
          <div className="v2-field-grid">
            <div className="v2-config-field">
              <Label>简历</Label>
              <Select value={resumeId} onValueChange={setResumeId} disabled={formDisabled}>
                <SelectTrigger className="v2-resume-select">
                  <SelectValue placeholder="请选择已解析简历" />
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
              label="面试类型"
              options={options?.interview_types ?? []}
              value={interviewType}
              disabled={formDisabled}
              onChange={(value) => {
                setInterviewType(value)
                setSelectedFocusTopics(buildRecommendedFocusTopics(value, targetRole))
              }}
            />
            <SegmentedControl
              label="目标岗位"
              options={options?.target_roles ?? []}
              value={targetRole}
              disabled={formDisabled}
              onChange={(value) => {
                setTargetRole(value)
                setSelectedFocusTopics(buildRecommendedFocusTopics(interviewType, value))
              }}
            />
            <SegmentedControl
              label="技术语言"
              options={options?.languages ?? []}
              value={language}
              disabled={formDisabled}
              onChange={setLanguage}
            />
            <SegmentedControl
              label="目标难度"
              options={options?.target_levels ?? []}
              value={targetLevel}
              disabled={formDisabled}
              onChange={setTargetLevel}
            />
          </div>

          <div className="v2-jd-panel">
            <div className="v2-jd-header">
              <div>
                <h3>JD 文本</h3>
                <p>可粘贴岗位描述；不填写时使用岗位通用模式。</p>
              </div>
              <Badge variant="secondary">{jdText.trim() ? '已提供 JD' : '未提供 JD'}</Badge>
            </div>
            <textarea
              className="v2-jd-textarea"
              value={jdText}
              maxLength={8000}
              disabled={formDisabled}
              placeholder="粘贴 JD 文本，可留空"
              onChange={(event) => setJdText(event.target.value)}
            />
          </div>

          <div className="v2-focus-panel">
            <div className="v2-focus-header">
              <span>系统推荐重点方向</span>
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
            {isSubmitting ? '正在生成面试计划…' : '生成面试计划'}
          </Button>
          </fieldset>
        </Card>
      </section>

      <LoadingOverlay open={isSubmitting} message="正在生成面试计划，请耐心等待" />
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

function readError(error: unknown) {
  return error instanceof Error ? error.message : '请求失败'
}
