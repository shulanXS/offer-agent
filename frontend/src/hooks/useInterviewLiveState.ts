/**R8：面试直播页状态机 hook。**

把 InterviewLivePage 的所有 useState / useRef / useEffect 状态机、消息流
处理、激活/收尾事件订阅、计时器等抽离到 hook。组件层只负责渲染。
*/
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  useActivateLiveInterview,
  useFinishLiveInterview,
  useLiveInterviewSession,
} from './useInterviewLive'
import { useInterviewPauseResume } from './useInterviewPauseResume'
import { evaluateInterview, subscribeInterviewEvents } from '@/services/interviewEvaluation'
import { replyLiveInterviewStream } from '@/services/interviewLive'
import i18n from '@/i18n'
import type { ChatMessage, StreamEvent } from '@/types'
import { isLiveInterviewSession, type LiveInterviewSessionDetail } from '@/types/interviewLive'
import { TypewriterStream } from '@/utils/typewriterStream'

export function useInterviewLiveState(token: string, sessionId: string, reviewMode: boolean) {
  const { t } = useTranslation('interview')
  const navigate = useNavigate()

  // ---- 基础状态 ----
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
  const [liveToast, setLiveToast] = useState<string | null>(null)

  // ---- 引用 ----
  const replyAbortRef = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement | null>(null)
  const autoFinishTriggeredRef = useRef(false)
  const warning60sTriggeredRef = useRef(false)
  const warning30sTriggeredRef = useRef(false)
  const postFinishTriggeredRef = useRef(false)

  // ---- 远端数据 ----
  const { data, isLoading, refetch } = useLiveInterviewSession(token, sessionId)
  const activateMutation = useActivateLiveInterview(token, sessionId)
  const finishMutation = useFinishLiveInterview(token, sessionId)

  // ---- 副作用：会话切换时重置 ----
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

  // ---- 同步远端 data → 本地状态 ----
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

  // ---- completed → 跳 evaluation 页 ----
  useEffect(() => {
    if (reviewMode || isLoading || !data || !isLiveInterviewSession(data)) return
    if (postFinishTriggeredRef.current || showEvalGeneratingOverlay) return
    if (data.status === 'completed') {
      navigate(`/interviews/${sessionId}/evaluation`, { replace: true })
    }
  }, [data, isLoading, navigate, reviewMode, sessionId, showEvalGeneratingOverlay])

  // ---- 暂停/恢复（hook 内部已封装） ----
  useInterviewPauseResume({
    sessionId,
    token,
    enabled: Boolean(sessionId) && sessionStatus === 'active',
  })

  // ---- 倒计时 ----
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

  // ---- 倒计时阈值告警 + auto-finish 触发 ----
  useEffect(() => {
    if (sessionStatus !== 'active') {
      autoFinishTriggeredRef.current = false
      setPendingAutoFinish(false)
      warning60sTriggeredRef.current = false
      warning30sTriggeredRef.current = false
      return
    }
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

  // ---- toast 5s 自动消失 ----
  useEffect(() => {
    if (!liveToast) return
    const timer = window.setTimeout(() => setLiveToast(null), 5000)
    return () => window.clearTimeout(timer)
  }, [liveToast])

  // ---- 自动收尾 ----
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
        if (session.status === 'evaluating') beginPostFinishFlow()
      } catch (err) {
        autoFinishTriggeredRef.current = false
        setError((err as Error).message || String(err))
      }
    })()
  }, [pendingAutoFinish, sessionStatus, isReplying, finishMutation])

  // ---- 滚动到底部 ----
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingAssistantId])

  // ---- 评估生成 + 事件订阅（post-finish） ----
  const beginPostFinishFlow = useCallback(() => {
    if (postFinishTriggeredRef.current || reviewMode) return
    postFinishTriggeredRef.current = true
    setShowEvalGeneratingOverlay(true)

    const fallbackTimer = window.setTimeout(() => {
      navigate('/interviews')
    }, 30_000)

    let es: EventSource | null = null
    const cleanup = () => {
      window.clearTimeout(fallbackTimer)
      es?.close()
    }

    try {
      es = subscribeInterviewEvents(
        sessionId,
        () => {
          cleanup()
          navigate(`/interviews/${sessionId}/evaluation`, { replace: true })
        },
        () => {
          /* 错误：忽略 */
        },
        () => {
          cleanup()
          navigate(`/interviews/${sessionId}/evaluation`, { replace: true })
        },
      )
    } catch {
      /* 订阅失败靠兜底 timer */
    }

    void evaluateInterview(token, sessionId).catch(() => {
      /* 评估失败靠兜底 timer */
    })
  }, [sessionId, token, navigate, reviewMode])

  // ---- 行为 ----
  const applyActivatedSession = useCallback((session: LiveInterviewSessionDetail) => {
    setMessages(session.messages)
    setSessionStatus(session.status)
    setProgress(session.progress)
    setTopicsPreview(session.topics_preview)
    setSessionTitle(session.title)
    setTargetRole(session.target_role)
    setRemainingSeconds(session.progress?.remaining_seconds ?? null)
  }, [])

  const handleActivate = useCallback(async () => {
    setError('')
    try {
      const session = await activateMutation.mutateAsync()
      applyActivatedSession(session)
      await refetch()
    } catch (err) {
      setError((err as Error).message || String(err))
    }
  }, [activateMutation, refetch, applyActivatedSession])

  const handleFinishConfirm = useCallback(async () => {
    setError('')
    try {
      const session = await finishMutation.mutateAsync()
      setMessages(session.messages)
      setSessionStatus(session.status)
      setProgress(session.progress)
      setRemainingSeconds(session.progress?.remaining_seconds ?? null)
      setShowFinishConfirm(false)
      if (session.status === 'evaluating') beginPostFinishFlow()
    } catch (err) {
      setError((err as Error).message || String(err))
    }
  }, [finishMutation, beginPostFinishFlow])

  const handleSubmit = useCallback(
    async (event?: React.FormEvent) => {
      event?.preventDefault()
      const content = draft.trim()
      if (!content) return
      const isCurrentlyReplying =
        sessionStatus === 'active' &&
        !isReplying &&
        !progress?.is_reply_processing &&
        !activateMutation.isPending &&
        !finishMutation.isPending
      if (!isCurrentlyReplying) return

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
          (streamEvent: StreamEvent) => {
            if (streamEvent.event === 'error') {
              const code = (streamEvent.data as { code?: string })?.code
              const message =
                (typeof streamEvent.data.message === 'string' && streamEvent.data.message) ||
                (code ? i18n.t(`errors:${code}`, { defaultValue: '' }) : '') ||
                i18n.t('errors:INTERVIEW_REPLY_FAILED')
              throw new Error(message)
            }
            if (streamEvent.event === 'session_state') {
              const nextStatus = streamEvent.data.status
              if (typeof nextStatus === 'string') {
                setSessionStatus(nextStatus as LiveInterviewSessionDetail['status'])
                if (nextStatus === 'evaluating' && !reviewMode) beginPostFinishFlow()
              }
              const nextProgress = streamEvent.data.progress
              if (nextProgress && typeof nextProgress === 'object') {
                const typed = nextProgress as LiveInterviewSessionDetail['progress']
                setProgress(typed)
                if (typed && typeof typed.remaining_seconds === 'number') {
                  setRemainingSeconds(typed.remaining_seconds)
                }
              }
            }
            if (streamEvent.event === 'progress') {
              const nextProgress = streamEvent.data as unknown as LiveInterviewSessionDetail['progress']
              setProgress(nextProgress)
              if (nextProgress && typeof nextProgress.remaining_seconds === 'number') {
                setRemainingSeconds(nextProgress.remaining_seconds)
              }
            }
            if (streamEvent.event === 'message_start') {
              const message = streamEvent.data.message as ChatMessage
              setStreamingAssistantId(message.id)
              typewriter.setTarget(message.id)
              setMessages((prev) => [...prev, { ...message, content: '' }])
            }
            if (streamEvent.event === 'delta') {
              typewriter.enqueue(String(streamEvent.data.delta ?? ''))
            }
            if (streamEvent.event === 'message_end') {
              finalAssistantMessage = streamEvent.data.message as ChatMessage
            }
            if (streamEvent.event === 'done') {
              const nextStatus = streamEvent.data.status
              if (typeof nextStatus === 'string') {
                setSessionStatus(nextStatus as LiveInterviewSessionDetail['status'])
              }
            }
          },
          { requestId, signal: controller.signal, retryOnError: true },
        )
        await typewriter.waitForIdle()
        if (finalAssistantMessage) {
          setMessages((prev) =>
            prev.map((item) =>
              item.id === finalAssistantMessage!.id ? finalAssistantMessage! : item,
            ),
          )
        }
        await refetch()
      } catch (err) {
        setError((err as Error).message || String(err))
        setMessages((prev) => prev.filter((item) => item.id !== optimisticUser.id))
      } finally {
        setIsReplying(false)
        setStreamingAssistantId('')
        replyAbortRef.current = null
      }
    },
    [
      draft,
      token,
      sessionId,
      messages,
      progress,
      sessionStatus,
      isReplying,
      activateMutation,
      finishMutation,
      reviewMode,
      beginPostFinishFlow,
      refetch,
    ],
  )

  return {
    state: {
      draft,
      messages,
      sessionTitle,
      targetRole,
      sessionStatus,
      progress,
      topicsPreview,
      error,
      isReplying,
      streamingAssistantId,
      showFinishConfirm,
      remainingSeconds,
      pendingAutoFinish,
      showEvalGeneratingOverlay,
      liveToast,
    },
    setters: {
      setDraft,
      setShowFinishConfirm,
      setError,
    },
    refs: {
      bottomRef,
      replyAbortRef,
    },
    data: { data, isLoading },
    mutations: { activateMutation, finishMutation, refetch },
    actions: {
      handleActivate,
      handleFinishConfirm,
      handleSubmit,
    },
  }
}
