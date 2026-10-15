import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { InterviewHeaderArt } from '@/components/InterviewHeaderArt'
import { LoadingOverlay } from '@/components/LoadingOverlay'
import { RegeneratePlanDialog } from '@/components/RegeneratePlanDialog'
import { CalendarClock, CheckCircle2, ClipboardList, Lock, RefreshCw, Sparkles } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'
import { useActivateLiveInterview } from '@/hooks/useInterviewLive'
import { useConfirmInterviewPlan, useInterviewPlanSessionDetail, useRegenerateInterviewPlan } from '@/hooks/useInterviewPlan'
import { isLiveInterviewSession } from '@/types/interviewLive'

interface InterviewPlanPageProps {
  token: string
}

export function InterviewPlanPage({ token }: InterviewPlanPageProps) {
  const { t } = useTranslation('plans')
  const { t: tInterview } = useTranslation('interview')
  const { t: tc } = useTranslation('common')
  const { sessionId = '' } = useParams()
  const navigate = useNavigate()
  const [regenerateDialogOpen, setRegenerateDialogOpen] = useState(false)
  const [actionError, setActionError] = useState('')

  const { data: sessionDetail, isLoading, error } = useInterviewPlanSessionDetail(token, sessionId)
  const regenerateMutation = useRegenerateInterviewPlan(token, sessionId)
  const confirmMutation = useConfirmInterviewPlan(token, sessionId)
  const activateMutation = useActivateLiveInterview(token, sessionId)
  const isStarting = confirmMutation.isPending || activateMutation.isPending
  const plan = sessionDetail?.plan ?? null
  const configuration = sessionDetail?.configuration ?? {}
  const isLocked = sessionDetail?.status === 'plan_confirmed'

  useEffect(() => {
    if (isLoading || !sessionDetail) return
    if (!isLiveInterviewSession(sessionDetail)) return

    const livePath = `/interviews/${sessionId}/live`
    if (sessionDetail.status === 'active') {
      navigate(livePath, { replace: true })
      return
    }
    if (sessionDetail.status === 'evaluating' || sessionDetail.status === 'completed') {
      navigate(`/interviews/${sessionId}/evaluation`, { replace: true })
    }
  }, [isLoading, navigate, sessionDetail, sessionId])

  async function handleConfirmAndStart() {
    setActionError('')
    try {
      if (!isLocked) {
        await confirmMutation.mutateAsync()
      }
      if (sessionDetail?.status !== 'active') {
        await activateMutation.mutateAsync()
      }
      navigate(`/interviews/${sessionId}/live`)
    } catch (err) {
      setActionError(err instanceof Error ? err.message : tc('request_failed'))
    }
  }

  if (isLoading) {
    return (
      <>
        <header className="v2-page-header">
          <div>
            <h2>{t('plan_title')}</h2>
            <p>{tc('loading')}</p>
          </div>
          <InterviewHeaderArt />
        </header>
      </>
    )
  }

  if (error || !plan) {
    return (
      <>
        <header className="v2-page-header">
          <div>
            <h2>{t('plan_title')}</h2>
            <p className="v2-error">{error ? (error instanceof Error ? error.message : tc('request_failed')) : '—'}</p>
          </div>
          <InterviewHeaderArt />
        </header>
        <div className="v2-plan-action-bar">
          <button type="button" className="v2-text-button" onClick={() => navigate('/interviews/new')}>
            {tc('back')}
          </button>
        </div>
      </>
    )
  }

  const summary = plan.candidate_summary
  const requiredCount = plan.topics_preview.filter((topic) => topic.required).length
  const canRegenerate = !isLocked && plan.regenerations_remaining > 0
  const canConfirm = !isLocked && sessionDetail?.status === 'plan_ready'

  return (
    <>
      <header className="v2-page-header">
        <div>
          <div className="v2-title-row">
            <h2>{t('plan_title')}</h2>
            {isLocked ? (
              <Badge variant="secondary" className="v2-plan-locked-badge">
                <Lock size={14} />
                {t('plan_status_confirmed')}
              </Badge>
            ) : null}
          </div>
          <p>{t('plan_subtitle')}</p>
        </div>
        <InterviewHeaderArt />
      </header>

      {actionError ? <p className="v2-error v2-plan-action-error">{actionError}</p> : null}

      {canRegenerate || canConfirm || isLocked ? (
        <div className="v2-plan-action-bar">
          {canRegenerate ? (
            <button
              type="button"
              className="v2-btn-regenerate"
              disabled={regenerateMutation.isPending || isStarting}
              onClick={() => setRegenerateDialogOpen(true)}
            >
              <RefreshCw size={16} />
              {t('btn_regenerate')} ({plan.regenerations_remaining})
            </button>
          ) : null}
          {canConfirm ? (
            <button
              type="button"
              className="v2-btn-confirm"
              disabled={regenerateMutation.isPending || isStarting}
              onClick={handleConfirmAndStart}
            >
              <CheckCircle2 size={16} />
              {isStarting ? tc('submitting') : t('btn_confirm')}
            </button>
          ) : null}
          {isLocked ? (
            <button type="button" className="v2-btn-confirm" disabled={isStarting} onClick={handleConfirmAndStart}>
              {isStarting ? tc('submitting') : t('btn_confirm')}
            </button>
          ) : null}
        </div>
      ) : null}

      <section className="v2-plan-layout">
        <Card className="v2-panel v2-plan-summary">
          <div className="v2-section-heading">
            <span className="v2-section-icon">
              <Sparkles />
            </span>
            <div>
              <h3>{t('plan_overview')}</h3>
              <p>
                v{plan.plan_version} ·{' '}
                {isLocked
                  ? t('plan_status_confirmed')
                  : `${plan.regenerations_remaining} left`}
              </p>
            </div>
          </div>

          <div className="v2-plan-meta-grid">
            <MetaItem label={tInterview('label_interview_type')} value={summary.interview_type_label} />
            <MetaItem label={tInterview('label_target_role')} value={summary.target_role_label} />
            <MetaItem label={tInterview('label_language')} value={summary.language_label} />
            <MetaItem label={tInterview('label_target_level')} value={summary.target_level_label} />
            <MetaItem label={tInterview('label_duration')} value={tc('minutes', { count: summary.duration_minutes })} />
            <MetaItem label="JD" value={summary.has_jd ? 'YES' : 'NO'} />
          </div>

          <div className="v2-plan-focus-block">
            <span>{t('plan_topics')}</span>
            <div className="v2-focus-options">
              {summary.focus_topics.map((topic) => (
                <Badge key={topic} variant="secondary">
                  {topic}
                </Badge>
              ))}
            </div>
          </div>

          <div className="v2-plan-reference-block">
            <span>{t('plan_candidate_summary')}</span>
            <ul>
              {summary.reference_summary.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        </Card>

        <div className="v2-plan-main-column">
          <Card className="v2-panel v2-plan-topics">
            <div className="v2-section-heading v2-plan-topics-heading">
              <span className="v2-section-icon">
                <ClipboardList />
              </span>
              <div>
                <h3>{t('plan_topics')}</h3>
                <p>
                  {plan.topics_preview.length} total, {requiredCount} required
                </p>
              </div>
              <span className="v2-plan-duration-chip">
                <CalendarClock size={15} />
                {tc('minutes', { count: 45 })}
              </span>
            </div>

            <div className="v2-plan-topic-list">
              {plan.topics_preview.map((topic, index) => (
                <article key={topic.id} className="v2-plan-topic-item">
                  <div className="v2-plan-topic-index">{index + 1}</div>
                  <div className="v2-plan-topic-body">
                    <div className="v2-plan-topic-title">
                      <h4>{topic.name}</h4>
                      <Badge variant="secondary" className={topic.required ? 'v2-badge-required' : undefined}>
                        {topic.required ? 'REQUIRED' : 'OPTIONAL'}
                      </Badge>
                    </div>
                    <p>{tc('minutes', { count: topic.estimated_minutes })}</p>
                  </div>
                </article>
              ))}
            </div>
          </Card>
        </div>
      </section>

      {isStarting ? <LoadingOverlay open message={tInterview('live_loading')} /> : null}

      <RegeneratePlanDialog
        open={regenerateDialogOpen}
        loading={regenerateMutation.isPending}
        regenerationsRemaining={plan.regenerations_remaining}
        configuration={configuration}
        onCancel={() => {
          if (!regenerateMutation.isPending) {
            setRegenerateDialogOpen(false)
            setActionError('')
          }
        }}
        onConfirm={(payload) => {
          setActionError('')
          regenerateMutation.mutate(payload, {
            onSuccess: () => {
              setRegenerateDialogOpen(false)
            },
            onError: (err) => {
              setActionError(err instanceof Error ? err.message : tc('request_failed'))
            },
          })
        }}
      />
    </>
  )
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="v2-plan-meta-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}
