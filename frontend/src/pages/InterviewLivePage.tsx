import { Card } from '@/components/ui/card'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { CandidateAvatar, InterviewerAvatar } from '@/components/InterviewAvatars'
import { LoadingOverlay } from '@/components/LoadingOverlay'
import { useInterviewOptions } from '@/hooks/useInterviewConfiguration'
import { useActivateLiveInterview, useFinishLiveInterview, useLiveInterviewSession } from '@/hooks/useInterviewLive'
import { evaluateInterview } from '@/services/interviewEvaluation'
import { replyLiveInterviewStream } from '@/services/interviewLive'
import type { ChatMessage, StreamEvent } from '@/types'
import { isLiveInterviewSession, type LiveInterviewSessionDetail } from '@/types/interviewLive'
import { BarChart3, BriefcaseBusiness, Clock3, LoaderCircle, MessageSquare, SendHorizonal } from 'lucide-react'
import { TypewriterStream } from '@/utils/typewriterStream'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'

interface InterviewLivePageProps {
  token: string
}

export function InterviewLivePage({ token }: InterviewLivePageProps) {
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
  const bottomRef = useRef<HTMLDivElement | null>(null)
  const autoFinishTriggeredRef = useRef(false)
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
      return
    }
    if (remainingSeconds !== 0) return
    setPendingAutoFinish(true)
  }, [remainingSeconds, sessionStatus])

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

    try {
      await replyLiveInterviewStream(token, sessionId, content, (event: StreamEvent) => {
        if (event.event === 'error') {
          const message = typeof event.data.message === 'string' ? event.data.message : '回复失败，请刷新页面后重试'
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
      })
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
            <h2>模拟面试</h2>
            <p className="v2-live-header-subtitle">正在加载会话…</p>
          </div>
        </header>
      </div>
    )
  }

  return (
    <div className="v2-live-page">
      <header className="v2-live-header">
        <div className="v2-live-header-top">
          <div className="v2-live-header-title-row">
            <h2>模拟面试</h2>
            <p className="v2-live-header-subtitle">{headerSubtitle}</p>
          </div>
          {!needsActivate && !isFinished ? (
            <button
              type="button"
              className="v2-live-end-btn"
              disabled={!canReply && !finishMutation.isPending}
              onClick={() => setShowFinishConfirm(true)}
            >
              <Clock3 size={16} />
              结束面试
            </button>
          ) : null}
        </div>

        {!needsActivate ? (
          <div className="v2-live-header-meta" aria-label="面试状态">
            <div className="v2-live-meta-item">
              <span className="v2-live-meta-icon" aria-hidden="true">
                <BriefcaseBusiness size={18} />
              </span>
              <div>
                <span className="v2-live-meta-label">当前职位</span>
                <strong>{roleLabel || sessionTitle || '—'}</strong>
              </div>
            </div>
            <div className="v2-live-meta-item">
              <span className="v2-live-meta-icon" aria-hidden="true">
                <BarChart3 size={18} />
              </span>
              <div>
                <span className="v2-live-meta-label">面试进度</span>
                <strong>{topicProgressLabel}</strong>
              </div>
            </div>
            <div className="v2-live-meta-item">
              <span className="v2-live-meta-icon" aria-hidden="true">
                <Clock3 size={18} />
              </span>
              <div>
                <span className="v2-live-meta-label">剩余时间</span>
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
              <h3>正在启动面试</h3>
              <p>正在生成首题，请稍候…</p>
            </>
          ) : (
            <>
              <MessageSquare size={28} />
              <h3>准备开始正式面试</h3>
              <p>将基于已锁定计划按考察方向依次提问。若刚从计划页进入，请返回计划页点击「确认并开始面试」以预生成首题。</p>
              <div className="v2-live-start-actions">
                <button type="button" className="v2-text-button" onClick={() => navigate(`/interviews/${sessionId}/plan`)}>
                  返回计划
                </button>
                {showManualStartButton ? (
                  <button type="button" className="v2-btn-confirm" onClick={() => void handleActivate()}>
                    开始面试
                  </button>
                ) : null}
              </div>
            </>
          )}
        </Card>
      ) : (
        <section className="v2-live-layout">
          <div className="v2-live-topic-bar">
            <span className="v2-live-topic-bar-label">当前主题</span>
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
                        面试官正在组织下一题…
                      </div>
                    </div>
                  </div>
                ) : null}
                <div ref={bottomRef} />
              </div>

              {isFinished ? (
                <div className="v2-live-finished">
                  <p>{reviewMode ? '对话记录只读查看。' : '本场面试已结束。'}</p>
                  <div className="v2-live-start-actions">
                    {!reviewMode && sessionStatus === 'evaluating' ? (
                      <button type="button" className="v2-btn-confirm" onClick={() => navigate('/interviews')}>
                        去面试记录
                      </button>
                    ) : null}
                    {sessionStatus === 'completed' ? (
                      <button
                        type="button"
                        className="v2-btn-confirm"
                        onClick={() => navigate(`/interviews/${sessionId}/evaluation`)}
                      >
                        查看评估报告
                      </button>
                    ) : null}
                    <button type="button" className="v2-text-button" onClick={() => navigate(`/interviews/${sessionId}/plan`)}>
                      返回计划页
                    </button>
                  </div>
                </div>
              ) : (
                <form className="v2-live-composer" onSubmit={handleSubmit}>
                  <textarea
                    value={draft}
                    placeholder="输入你的回答..."
                    rows={4}
                    disabled={!canReply}
                    onChange={(event) => setDraft(event.target.value)}
                    onKeyDown={handleComposerKeyDown}
                  />
                  <div className="v2-live-composer-footer">
                    <span className="v2-live-composer-hint">Enter 发送，Shift + Enter 换行</span>
                    <button type="submit" className="v2-btn-confirm v2-live-send-btn" disabled={!canReply || !draft.trim()}>
                      <SendHorizonal size={16} />
                      发送
                    </button>
                  </div>
                </form>
              )}
            </Card>
          </section>
      )}

      <ConfirmDialog
        open={showFinishConfirm}
        title="确认结束面试？"
        description="结束后将无法继续回答。系统会保存当前进度并进入评估状态。"
        confirmLabel="结束面试"
        cancelLabel="继续面试"
        loading={finishMutation.isPending}
        danger
        onConfirm={handleFinishConfirm}
        onCancel={() => setShowFinishConfirm(false)}
      />

      <LoadingOverlay
        open={showEvalGeneratingOverlay}
        message="正在生成评估报告，请稍后去面试记录页查看"
        hideLabel
      />
    </div>
  )
}

function InterviewMessage({ message }: { message: ChatMessage }) {
  const isAssistant = message.role === 'assistant'
  const displayName = isAssistant ? '面试官' : '你'
  const timestamp = formatMessageTime(message.created_at)
  const Avatar = isAssistant ? InterviewerAvatar : CandidateAvatar

  return (
    <article className={`v2-live-thread ${isAssistant ? 'assistant' : 'user'}`}>
      <div className="v2-live-thread-head">
        <Avatar />
        <div className="v2-live-thread-meta">
          <strong>{displayName}</strong>
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
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
}

function readError(error: unknown) {
  return error instanceof Error ? error.message : '请求失败'
}
