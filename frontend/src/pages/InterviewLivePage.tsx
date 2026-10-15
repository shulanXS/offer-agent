import { Card } from '@/components/ui/card'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { AlgorithmTurn } from '@/components/AlgorithmTurn'
import { CandidateAvatar, InterviewerAvatar } from '@/components/InterviewAvatars'
import { LoadingOverlay } from '@/components/LoadingOverlay'
import { useInterviewOptions } from '@/hooks/useInterviewConfiguration'
import { useActivateLiveInterview, useFinishLiveInterview, useLiveInterviewSession } from '@/hooks/useInterviewLive'
import { useInterviewPauseResume } from '@/hooks/useInterviewPauseResume'
import { evaluateInterview } from '@/services/interviewEvaluation'
import { replyLiveInterviewStream } from '@/services/interviewLive'
import { bcp47ForIntl } from '@/i18n/useLocale'
import i18n from '@/i18n'
import type { ChatMessage, StreamEvent } from '@/types'
import { isLiveInterviewSession, type LiveInterviewSessionDetail } from '@/types/interviewLive'
import { BarChart3, BriefcaseBusiness, Clock3, Code2, LoaderCircle, MessageSquare, SendHorizonal, X } from 'lucide-react'
import { TypewriterStream } from '@/utils/typewriterStream'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'

interface InterviewLivePageProps {
  token: string
}

export function InterviewLivePage({ token }: InterviewLivePageProps) {
  const { t } = useTranslation('interview')
  const { t: tc } = useTranslation('common')
  const { sessionId = '' } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const reviewMode = searchParams.get('review') === '1'
  const [draft, setDraft] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [sessionTitle, setSessionTitle] = useState('')
  const [targetRole, setTargetRole] = useState('')
  const [sessionStatus, setSessionStatus] = useState<LiveInterviewSessionDetail['status'] | 'plan_confirmed'>(
    'plan_confirmed',
  )
  const [progress, setProgress] = useState<LiveInterviewSessionDetail['progress']>(null)
  const [topicsPreview, setTopicsPreview] = useState<LiveInterviewSessionDetail['topics_preview']>([])
  const [error, setError] = useState('')
  const [isReplying, setIsReplying] = useState(false)
  const [streamingAssistantId, setStreamingAssistantId] = useState('')
  const [showFinishConfirm, setShowFinishConfirm] = useState(false)
  const [remainingSeconds, setRemainingSeconds] = useState<number | null>(null)
  const [pendingAutoFinish, setPendingAutoFinish] = useState(false)
  const [showEvalGeneratingOverlay, setShowEvalGeneratingOverlay] = useState(false)
  const [isAlgoPanelOpen, setIsAlgoPanelOpen] = useState(false)
  const [algoResult, setAlgoResult] = useState<{ problem_id: string; overall: number } | null>(null)
  const replyAbortRef = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement | null>(null)

  // v1.1: 离开/回到页面时冻结/恢复面试计时
  useInterviewPauseResume({
    sessionId,
    token,
    enabled: Boolean(sessionId) && sessionStatus === 'active',
  })
  const autoFinishTriggeredRef = useRef(false)
  const warning60sTriggeredRef = useRef(false)
  const warning30sTriggeredRef = useRef(false)
  const [liveToast, setLiveToast] = useState<string | null>(null)
  const postFinishTriggeredRef = useRef(false)

  const { data, isLoading, refetch } = useLiveInterviewSession(token, sessionId)
  const { data: interviewOptions } = useInterviewOptions(token)
  const activateMutation = useActivateLiveInterview(token, sessionId)
  const finishMutation = useFinishLiveInterview(token, sessionId)

  useEffect(() => {
    setDraft('')
    setMessages([])
    setSessionTitle('')
    setTargetRole('')
    setSessionStatus('plan_confirmed')
    setProgress(null)
    setTopicsPreview([])
    setError('')
    setIsReplying(false)
    setStreamingAssistantId('')
    setShowFinishConfirm(false)
    setRemainingSeconds(null)
    setPendingAutoFinish(false)
    setShowEvalGeneratingOverlay(false)
    autoFinishTriggeredRef.current = false
    postFinishTriggeredRef.current = false
  }, [sessionId, reviewMode])

  useEffect(() => {
    if (!data) return
    if (isLiveInterviewSession(data)) {
      setMessages(data.messages)
      setSessionStatus(data.status)
      setProgress(data.progress)
      setTopicsPreview(data.topics_preview)
      setSessionTitle(data.title)
      setTargetRole(data.target_role)
      if (data.status === 'active') {
        setRemainingSeconds(data.progress?.remaining_seconds ?? null)
      } else if (data.progress?.remaining_seconds != null) {
        setRemainingSeconds(data.progress.remaining_seconds)
      }
    }
  }, [data])

  useEffect(() => {
    if (reviewMode || isLoading || !data || !isLiveInterviewSession(data)) return
    if (postFinishTriggeredRef.current || showEvalGeneratingOverlay) return
    if (data.status === 'completed') {
      navigate(`/interviews/${sessionId}/evaluation`, { replace: true })
    }
  }, [data, isLoading, navigate, reviewMode, sessionId, showEvalGeneratingOverlay])

  function applyActivatedSession(session: LiveInterviewSessionDetail) {
    setMessages(session.messages)
    setSessionStatus(session.status)
    setProgress(session.progress)
    setTopicsPreview(session.topics_preview)
    setSessionTitle(session.title)
    setTargetRole(session.target_role)
    setRemainingSeconds(session.progress?.remaining_seconds ?? null)
  }

  function beginPostFinishFlow() {
    if (postFinishTriggeredRef.current || reviewMode) return
    postFinishTriggeredRef.current = true
    setShowEvalGeneratingOverlay(true)
    void evaluateInterview(token, sessionId).catch(() => {
      // 评估可在面试记录页重试
    })
    window.setTimeout(() => {
      navigate('/interviews')
    }, 3000)
  }

  useEffect(() => {
    if (sessionStatus !== 'active') return

    const timer = window.setInterval(() => {
      setRemainingSeconds((prev) => {
        if (prev === null || prev <= 0) return 0
        return prev - 1
      })
    }, 1000)

    return () => window.clearInterval(timer)
  }, [sessionStatus])

  useEffect(() => {
    if (sessionStatus !== 'active') {
      autoFinishTriggeredRef.current = false
      setPendingAutoFinish(false)
      warning60sTriggeredRef.current = false
      warning30sTriggeredRef.current = false
      return
    }
    // 5.7：60 秒 / 30 秒缓冲提示（只触发一次）
    if (remainingSeconds === 60 && !warning60sTriggeredRef.current) {
      warning60sTriggeredRef.current = true
      setLiveToast(t('countdown_warning_60'))
    } else if (remainingSeconds === 30 && !warning30sTriggeredRef.current) {
      warning30sTriggeredRef.current = true
      setLiveToast(t('countdown_warning_30'))
    }
    if (remainingSeconds !== 0) return
    setPendingAutoFinish(true)
  }, [remainingSeconds, sessionStatus, t])

  useEffect(() => {
    if (!pendingAutoFinish || sessionStatus !== 'active' || autoFinishTriggeredRef.current) return
    if (isReplying || finishMutation.isPending) return

    autoFinishTriggeredRef.current = true
    setPendingAutoFinish(false)

    void (async () => {
      setError('')
      try {
        const session = await finishMutation.mutateAsync()
        setMessages(session.messages)
        setSessionStatus(session.status)
        setProgress(session.progress)
        setRemainingSeconds(session.progress?.remaining_seconds ?? null)
        if (session.status === 'evaluating') {
          beginPostFinishFlow()
        }
      } catch (err) {
        autoFinishTriggeredRef.current = false
        setError(readError(err))
      }
    })()
  }, [pendingAutoFinish, sessionStatus, isReplying, finishMutation])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingAssistantId])

  const canReply =
    sessionStatus === 'active' &&
    !isReplying &&
    !progress?.is_reply_processing &&
    !activateMutation.isPending &&
    !finishMutation.isPending
  const isFinished = sessionStatus === 'evaluating' || sessionStatus === 'completed'
  const needsActivate = !isLiveInterviewSession(data) || sessionStatus === 'plan_confirmed'
  const isStartingInterview = needsActivate && activateMutation.isPending
  const showManualStartButton = needsActivate && !isStartingInterview
  const showReplyWaiting =
    !streamingAssistantId && (isReplying || Boolean(progress?.is_reply_processing))

  const roleLabel = useMemo(
    () => resolveRoleLabel(targetRole, interviewOptions?.target_roles),
    [interviewOptions?.target_roles, targetRole],
  )

  const remainingTimeLabel = useMemo(() => formatRemainingTime(remainingSeconds), [remainingSeconds])

  const topicProgressLabel = useMemo(() => {
    const completed = progress?.completed_topic_count ?? 0
    const total = progress?.total_topic_count ?? topicsPreview.length
    return `${completed} / ${total}`
  }, [progress, topicsPreview.length])

  const headerSubtitle = useMemo(() => {
    if (needsActivate) return '请先在计划页确认并锁定计划；也可在此生成首题后开始对话。'
    const topicCount = progress?.total_topic_count ?? topicsPreview.length
    return `本次预计 45 分钟，将覆盖约 ${topicCount || '4–5'} 个能力方向。系统会根据你的回答动态追问或切换主题，单个方向最多追问两次。`
  }, [needsActivate, progress?.total_topic_count, topicsPreview.length])

  async function handleActivate() {
    setError('')
    try {
      const session = await activateMutation.mutateAsync()
      applyActivatedSession(session)
      await refetch()
    } catch (err) {
      setError(readError(err))
    }
  }

  async function handleFinishConfirm() {
    setError('')
    try {
      const session = await finishMutation.mutateAsync()
      setMessages(session.messages)
      setSessionStatus(session.status)
      setProgress(session.progress)
      setRemainingSeconds(session.progress?.remaining_seconds ?? null)
      setShowFinishConfirm(false)
      if (session.status === 'evaluating') {
        beginPostFinishFlow()
      }
    } catch (err) {
      setError(readError(err))
    }
  }

  async function handleSubmit(event?: React.FormEvent) {
    event?.preventDefault()
    const content = draft.trim()
    if (!content || !canReply) return

    setError('')
    setIsReplying(true)
    setDraft('')

    const optimisticUser: ChatMessage = {
      id: `temp-user-${Date.now()}`,
      session_id: sessionId,
      seq: messages.length + 1,
      role: 'user',
      kind: 'answer',
      content,
      created_at: new Date().toISOString(),
      meta: { topic_id: progress?.current_topic_id ?? '' },
    }
    setMessages((prev) => [...prev, optimisticUser])

    const typewriter = new TypewriterStream((targetId, content) => {
      setMessages((prev) => prev.map((item) => (item.id === targetId ? { ...item, content } : item)))
    })
    let finalAssistantMessage: ChatMessage | null = null
    const requestId = `web-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    const controller = new AbortController()
    replyAbortRef.current = controller

    try {
      await replyLiveInterviewStream(
        token,
        sessionId,
        content,
        (event: StreamEvent) => {
        if (event.event === 'error') {
          const code = (event.data as { code?: string })?.code
          const message =
            (typeof event.data.message === 'string' && event.data.message) ||
            (code ? i18n.t(`errors:${code}`, { defaultValue: '' }) : '') ||
            i18n.t('errors:INTERVIEW_REPLY_FAILED')
          throw new Error(message)
        }
        if (event.event === 'session_state') {
          const nextStatus = event.data.status
          if (typeof nextStatus === 'string') {
            setSessionStatus(nextStatus as LiveInterviewSessionDetail['status'])
            if (nextStatus === 'evaluating' && !reviewMode) {
              beginPostFinishFlow()
            }
          }
          const nextProgress = event.data.progress
          if (nextProgress && typeof nextProgress === 'object') {
            const typed = nextProgress as LiveInterviewSessionDetail['progress']
            setProgress(typed)
            if (typed && typeof typed.remaining_seconds === 'number') {
              setRemainingSeconds(typed.remaining_seconds)
            }
          }
        }
        if (event.event === 'progress') {
          const nextProgress = event.data as unknown as LiveInterviewSessionDetail['progress']
          setProgress(nextProgress)
          if (nextProgress && typeof nextProgress.remaining_seconds === 'number') {
            setRemainingSeconds(nextProgress.remaining_seconds)
          }
        }
        if (event.event === 'message_start') {
          const message = event.data.message as ChatMessage
          setStreamingAssistantId(message.id)
          typewriter.setTarget(message.id)
          setMessages((prev) => [...prev, { ...message, content: '' }])
        }
        if (event.event === 'delta') {
          typewriter.enqueue(String(event.data.delta ?? ''))
        }
        if (event.event === 'message_end') {
          finalAssistantMessage = event.data.message as ChatMessage
        }
        if (event.event === 'done') {
          const nextStatus = event.data.status
          if (typeof nextStatus === 'string') {
            setSessionStatus(nextStatus as LiveInterviewSessionDetail['status'])
          }
        }
      },
        {
          requestId,
          signal: controller.signal,
          retryOnError: true,
        },
      )
      await typewriter.waitForIdle()
      if (finalAssistantMessage) {
        setMessages((prev) =>
          prev.map((item) => (item.id === finalAssistantMessage!.id ? finalAssistantMessage! : item)),
        )
      }
      await refetch()
    } catch (err) {
      setError(readError(err))
      setMessages((prev) => prev.filter((item) => item.id !== optimisticUser.id))
      await refetch()
    } finally {
      setIsReplying(false)
      setStreamingAssistantId('')
    }
  }

  function handleComposerKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void handleSubmit()
    }
  }

  if (isLoading) {
    return (
      <div className="v2-live-page">
        <header className="v2-live-header">
          <div className="v2-live-header-title-row">
            <h2>{t('live_title')}</h2>
            <p className="v2-live-header-subtitle">{t('live_loading')}</p>
          </div>
        </header>
      </div>
    )
  }

  useEffect(() => {
    if (!liveToast) return
    const timer = window.setTimeout(() => setLiveToast(null), 5000)
    return () => window.clearTimeout(timer)
  }, [liveToast])

  return (
    <div className="v2-live-page">
      {liveToast ? (
        <div className="v2-live-toast" role="status" aria-live="polite">
          {liveToast}
        </div>
      ) : null}
      <header className="v2-live-header">
        <div className="v2-live-header-top">
          <div className="v2-live-header-title-row">
            <h2>{t('live_title')}</h2>
            <p className="v2-live-header-subtitle">{headerSubtitle}</p>
          </div>
          {!needsActivate && !isFinished ? (
            <div className="v2-live-header-actions">
              {data && isLiveInterviewSession(data) && data.configuration?.include_algorithm ? (
                <button
                  type="button"
                  className="v2-live-algo-btn"
                  onClick={() => setIsAlgoPanelOpen((v) => !v)}
                  aria-pressed={isAlgoPanelOpen}
                >
                  <Code2 size={16} />
                  {isAlgoPanelOpen ? t('algo_close') : t('algo_open')}
                </button>
              ) : null}
              <button
                type="button"
                className="v2-live-end-btn"
                disabled={!canReply && !finishMutation.isPending}
                onClick={() => setShowFinishConfirm(true)}
              >
                <Clock3 size={16} />
                {t('live_end_btn')}
              </button>
            </div>
          ) : null}
        </div>

        {!needsActivate ? (
          <div className="v2-live-header-meta" aria-label="Interview status">
            <div className="v2-live-meta-item">
              <span className="v2-live-meta-icon" aria-hidden="true">
                <BriefcaseBusiness size={18} />
              </span>
              <div>
                <span className="v2-live-meta-label">{t('live_meta_role')}</span>
                <strong>{roleLabel || sessionTitle || '—'}</strong>
              </div>
            </div>
            <div className="v2-live-meta-item">
              <span className="v2-live-meta-icon" aria-hidden="true">
                <BarChart3 size={18} />
              </span>
              <div>
                <span className="v2-live-meta-label">{t('live_topic_progress')}</span>
                <strong>{topicProgressLabel}</strong>
              </div>
            </div>
            <div className="v2-live-meta-item">
              <span className="v2-live-meta-icon" aria-hidden="true">
                <Clock3 size={18} />
              </span>
              <div>
                <span className="v2-live-meta-label">{t('live_remaining')}</span>
                <strong
                  className={`v2-live-countdown ${progress?.is_wrap_up_zone || remainingSeconds === 0 ? 'v2-live-remaining-warning' : ''}`}
                >
                  {remainingTimeLabel}
                </strong>
              </div>
            </div>
          </div>
        ) : null}
      </header>

      {error ? <p className="v2-error v2-live-error">{error}</p> : null}

      {needsActivate ? (
        <Card className="v2-panel v2-live-start-card">
          {isStartingInterview ? (
            <>
              <LoaderCircle className="v2-spin" size={28} />
              <h3>{tc('loading')}</h3>
              <p>{t('live_loading')}</p>
            </>
          ) : (
            <>
              <MessageSquare size={28} />
              <h3>{t('live_activate_btn')}</h3>
              <p>{t('live_subtitle')}</p>
              <div className="v2-live-start-actions">
                <button type="button" className="v2-text-button" onClick={() => navigate(`/interviews/${sessionId}/plan`)}>
                  {tc('back')}
                </button>
                {showManualStartButton ? (
                  <button type="button" className="v2-btn-confirm" onClick={() => void handleActivate()}>
                    {t('live_activate_btn')}
                  </button>
                ) : null}
              </div>
            </>
          )}
        </Card>
      ) : (
        <section className="v2-live-layout">
          <div className="v2-live-topic-bar">
            <span className="v2-live-topic-bar-label">{t('live_current_topic')}</span>
            <span className="v2-live-topic-tag">{progress?.current_topic_name || '—'}</span>
          </div>
          <Card className="v2-panel v2-live-chat">
              <div className="v2-live-message-list">
                {messages.map((message) => (
                  <InterviewMessage key={message.id} message={message} />
                ))}
                {showReplyWaiting ? (
                  <div className="v2-live-streaming">
                    <div className="v2-live-thread-head">
                      <InterviewerAvatar />
                      <div className="v2-live-streaming-copy">
                        <LoaderCircle className="v2-spin" size={16} />
                        {t('live_typing')}
                      </div>
                    </div>
                  </div>
                ) : null}
                <div ref={bottomRef} />
              </div>

              {isFinished ? (
                <div className="v2-live-finished">
                  <p>{t('live_status_completed')}</p>
                  <div className="v2-live-start-actions">
                    {!reviewMode && sessionStatus === 'evaluating' ? (
                      <button type="button" className="v2-btn-confirm" onClick={() => navigate('/interviews')}>
                        Records
                      </button>
                    ) : null}
                    {sessionStatus === 'completed' ? (
                      <button
                        type="button"
                        className="v2-btn-confirm"
                        onClick={() => navigate(`/interviews/${sessionId}/evaluation`)}
                      >
                        Evaluation
                      </button>
                    ) : null}
                    <button type="button" className="v2-text-button" onClick={() => navigate(`/interviews/${sessionId}/plan`)}>
                      {tc('back')}
                    </button>
                  </div>
                </div>
              ) : (
                <form className="v2-live-composer" onSubmit={handleSubmit}>
                  <textarea
                    value={draft}
                    placeholder={t('live_composer_placeholder')}
                    rows={4}
                    disabled={!canReply}
                    onChange={(event) => setDraft(event.target.value)}
                    onKeyDown={handleComposerKeyDown}
                  />
                  <div className="v2-live-composer-footer">
                    <span className="v2-live-composer-hint">Enter ↵</span>
                    <button type="submit" className="v2-btn-confirm v2-live-send-btn" disabled={!canReply || !draft.trim()}>
                      <SendHorizonal size={16} />
                      {t('live_send')}
                    </button>
                  </div>
                </form>
              )}
            </Card>
          </section>
      )}

      {isAlgoPanelOpen ? (
        <aside className="v2-algo-panel" role="complementary" aria-label={t('algo_title')}>
          <header className="v2-algo-panel-head">
            <h3>{t('algo_title')}</h3>
            <button
              type="button"
              className="v2-algo-panel-close"
              onClick={() => setIsAlgoPanelOpen(false)}
              aria-label={tc('close')}
            >
              <X size={18} />
            </button>
          </header>
          <AlgorithmTurn
            token={token}
            problemId={algoResult?.problem_id || 'two_sum'}
            disabled={!canReply}
            onResult={(r) => {
              setAlgoResult({ problem_id: r.problem_id, overall: r.overall })
            }}
          />
          {algoResult ? (
            <p className="v2-algo-panel-result">
              {t('algo_result_overall', { score: algoResult.overall.toFixed(1) })}
            </p>
          ) : null}
        </aside>
      ) : null}

      <ConfirmDialog
        open={showFinishConfirm}
        title={t('live_finish_confirm_title')}
        description={t('live_finish_confirm_body')}
        confirmLabel={t('live_end_btn')}
        cancelLabel={t('live_send')}
        loading={finishMutation.isPending}
        danger
        onConfirm={handleFinishConfirm}
        onCancel={() => setShowFinishConfirm(false)}
      />

      <LoadingOverlay
        open={showEvalGeneratingOverlay}
        message={t('live_eval_overlay')}
        hideLabel
      />
    </div>
  )
}

function InterviewMessage({ message }: { message: ChatMessage }) {
  const { t } = useTranslation('interview')
  const isAssistant = message.role === 'assistant'
  const displayName = isAssistant ? t('live_send') /* interviewer label fallback */ : t('live_send')
  // 简单 label：assistant 显示 Interviewer/面试官，user 显示 You/你
  const interviewerLabel = (i18n.language || 'en').startsWith('zh') ? '面试官' : 'Interviewer'
  const youLabel = (i18n.language || 'en').startsWith('zh') ? '你' : 'You'
  const finalName = isAssistant ? interviewerLabel : youLabel
  void displayName // keep
  const timestamp = formatMessageTime(message.created_at)
  const Avatar = isAssistant ? InterviewerAvatar : CandidateAvatar

  return (
    <article className={`v2-live-thread ${isAssistant ? 'assistant' : 'user'}`}>
      <div className="v2-live-thread-head">
        <Avatar />
        <div className="v2-live-thread-meta">
          <strong>{finalName}</strong>
          {timestamp ? <time dateTime={message.created_at}>{timestamp}</time> : null}
        </div>
      </div>
      <div className="v2-live-thread-content">
        <div className="v2-live-bubble">{message.content}</div>
      </div>
    </article>
  )
}

function resolveRoleLabel(targetRole: string, options?: Array<{ value: string; label: string }>) {
  if (!targetRole) return ''
  const matched = options?.find((item) => item.value === targetRole)
  if (matched) return matched.label
  const fallback: Record<string, string> = {
    backend: '后端开发工程师',
    frontend: '前端开发工程师',
    fullstack: '全栈开发工程师',
    agent: 'Agent 工程师',
    product: '产品经理',
  }
  return fallback[targetRole] ?? targetRole
}

function formatRemainingTime(seconds: number | null) {
  if (seconds === null) return '—'
  if (seconds <= 0) return '00:00'
  const minutes = Math.floor(seconds / 60)
  const rest = seconds % 60
  return `${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}`
}

function formatMessageTime(value: string) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const locale = (i18n.language || 'en').startsWith('zh') ? 'zh-CN' : 'en-US'
  return date.toLocaleTimeString(bcp47ForIntl(locale === 'zh-CN' ? 'zh' : 'en'), {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

function readError(error: unknown) {
  return error instanceof Error ? error.message : '请求失败'
}
