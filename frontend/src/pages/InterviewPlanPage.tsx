import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { InterviewHeaderArt } from '@/components/InterviewHeaderArt'
import { LoadingOverlay } from '@/components/LoadingOverlay'
import { RegeneratePlanDialog } from '@/components/RegeneratePlanDialog'
import { CalendarClock, CheckCircle2, ClipboardList, Lock, RefreshCw, Sparkles } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useActivateLiveInterview } from '@/hooks/useInterviewLive'
import { useConfirmInterviewPlan, useInterviewPlanSessionDetail, useRegenerateInterviewPlan } from '@/hooks/useInterviewPlan'
import { isLiveInterviewSession } from '@/types/interviewLive'

interface InterviewPlanPageProps {
  token: string
}

export function InterviewPlanPage({ token }: InterviewPlanPageProps) {
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
      setActionError(readError(err))
    }
  }

  if (isLoading) {
    return (
      <>
        <header className="v2-page-header">
          <div>
            <h2>面试计划</h2>
            <p>正在加载计划摘要…</p>
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
            <h2>面试计划</h2>
            <p className="v2-error">{error ? readError(error) : '暂无计划数据'}</p>
          </div>
          <InterviewHeaderArt />
        </header>
        <div className="v2-plan-action-bar">
          <button type="button" className="v2-text-button" onClick={() => navigate('/interviews/new')}>
            返回配置
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
            <h2>面试计划预览</h2>
            {isLocked ? (
              <Badge variant="secondary" className="v2-plan-locked-badge">
                <Lock size={14} />
                计划已锁定
              </Badge>
            ) : null}
          </div>
          <p>
            {isLocked
              ? '计划已确认，可继续进入正式面试。'
              : '确认考察方向与参考摘要；完整开场题与追问话术不会在此展示。'}
          </p>
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
              重新生成（剩余 {plan.regenerations_remaining} 次）
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
              {isStarting ? '正在进入…' : '确认并开始面试'}
            </button>
          ) : null}
          {isLocked ? (
            <button type="button" className="v2-btn-confirm" disabled={isStarting} onClick={handleConfirmAndStart}>
              {isStarting ? '正在进入…' : '继续面试'}
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
              <h3>计划摘要</h3>
              <p>
                版本 {plan.plan_version}
                {isLocked ? ' · 已锁定' : ` · 还可重新生成 ${plan.regenerations_remaining} 次`}
              </p>
            </div>
          </div>

          <div className="v2-plan-meta-grid">
            <MetaItem label="面试类型" value={summary.interview_type_label} />
            <MetaItem label="目标岗位" value={summary.target_role_label} />
            <MetaItem label="技术语言" value={summary.language_label} />
            <MetaItem label="目标难度" value={summary.target_level_label} />
            <MetaItem label="预计时长" value={`${summary.duration_minutes} 分钟`} />
            <MetaItem label="JD" value={summary.has_jd ? '已提供' : '未提供'} />
          </div>

          <div className="v2-plan-focus-block">
            <span>用户选择的重点方向</span>
            <div className="v2-focus-options">
              {summary.focus_topics.map((topic) => (
                <Badge key={topic} variant="secondary">
                  {topic}
                </Badge>
              ))}
            </div>
          </div>

          <div className="v2-plan-reference-block">
            <span>参考摘要</span>
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
                <h3>考察方向</h3>
                <p>
                  共 {plan.topics_preview.length} 个方向，其中 {requiredCount} 个必考
                </p>
              </div>
              <span className="v2-plan-duration-chip">
                <CalendarClock size={15} />
                45 分钟
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
                        {topic.required ? '必考' : '选考'}
                      </Badge>
                    </div>
                    <p>预计 {topic.estimated_minutes} 分钟</p>
                  </div>
                </article>
              ))}
            </div>
          </Card>
        </div>
      </section>

      {isStarting ? <LoadingOverlay open message="正在生成首题，请稍候…" /> : null}

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
              setActionError(readError(err))
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

function readError(error: unknown) {
  return error instanceof Error ? error.message : '请求失败'
}
