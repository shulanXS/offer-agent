/**R8 重构：状态机抽到 useInterviewLiveState，渲染拆为 5 个子组件。*/
import { useState, useMemo, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { AlgorithmTurn } from '@/components/AlgorithmTurn'
import { LoadingOverlay } from '@/components/LoadingOverlay'
import { useInterviewOptions } from '@/hooks/useInterviewConfiguration'
import { useInterviewLiveState } from '@/hooks/useInterviewLiveState'
import { InterviewLiveHeader } from '@/components/interview/InterviewLiveHeader'
import { InterviewLiveStartCard } from '@/components/interview/InterviewLiveStartCard'
import { InterviewLiveTopicBar } from '@/components/interview/InterviewLiveTopicBar'
import { InterviewLiveChat } from '@/components/interview/InterviewLiveChat'
import { InterviewLiveComposer } from '@/components/interview/InterviewLiveComposer'
import { isLiveInterviewSession } from '@/types/interviewLive'

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
  const [isAlgoPanelOpen, setIsAlgoPanelOpen] = useState(false)
  const [algoResult, setAlgoResult] = useState<{ problem_id: string; overall: number } | null>(null)

  const { state, setters, refs, data, mutations, actions } = useInterviewLiveState(
    token,
    sessionId,
    reviewMode,
  )
  const { data: interviewOptions } = useInterviewOptions(token)

  const roleLabel = useMemo(() => {
    if (!state.targetRole) return ''
    const opts = interviewOptions?.target_roles
    const matched = opts?.find((item) => item.value === state.targetRole)
    if (matched) return matched.label
    const fallback: Record<string, string> = {
      backend: t('role_fallback_backend'),
      frontend: t('role_fallback_frontend'),
      fullstack: t('role_fallback_fullstack'),
      agent: t('role_fallback_agent'),
      product: t('role_fallback_product'),
    }
    return fallback[state.targetRole] ?? state.targetRole
  }, [interviewOptions?.target_roles, state.targetRole, t])

  const remainingTimeLabel = useMemo(() => formatRemainingTime(state.remainingSeconds), [state.remainingSeconds])
  const topicProgressLabel = useMemo(() => {
    const completed = state.progress?.completed_topic_count ?? 0
    const total = state.progress?.total_topic_count ?? state.topicsPreview.length
    return `${completed} / ${total}`
  }, [state.progress, state.topicsPreview.length])

  const headerSubtitle = useMemo(() => {
    const needsActivate = !isLiveInterviewSession(data.data) || state.sessionStatus === 'plan_confirmed'
    if (needsActivate) return t('live_subtitle_needs_activate')
    const topicCount = state.progress?.total_topic_count ?? state.topicsPreview.length
    return t('live_subtitle_default', { minutes: 45, topics: topicCount || '4–5' })
  }, [data.data, state.sessionStatus, state.progress, state.topicsPreview.length, t])

  const canReply =
    state.sessionStatus === 'active' &&
    !state.isReplying &&
    !state.progress?.is_reply_processing &&
    !mutations.activateMutation.isPending &&
    !mutations.finishMutation.isPending
  const isFinished = state.sessionStatus === 'evaluating' || state.sessionStatus === 'completed'
  const needsActivate = !isLiveInterviewSession(data.data) || state.sessionStatus === 'plan_confirmed'
  const isStartingInterview = needsActivate && mutations.activateMutation.isPending
  const showManualStartButton = needsActivate && !isStartingInterview
  const showReplyWaiting =
    !state.streamingAssistantId && (state.isReplying || Boolean(state.progress?.is_reply_processing))

  const handleComposerKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault()
        void actions.handleSubmit()
      }
    },
    [actions],
  )

  if (data.isLoading) {
    return (
      <div className="app-live-page">
        <header className="app-live-header">
          <div className="app-live-header-title-row">
            <h2>{t('live_title')}</h2>
            <p className="app-live-header-subtitle">{t('live_loading')}</p>
          </div>
        </header>
      </div>
    )
  }

  return (
    <div className="app-live-page">
      {state.liveToast ? (
        <div className="app-live-toast" role="status" aria-live="polite">
          {state.liveToast}
        </div>
      ) : null}

      <InterviewLiveHeader
        sessionTitle={state.sessionTitle}
        targetRoleLabel={roleLabel}
        remainingTimeLabel={remainingTimeLabel}
        topicProgressLabel={topicProgressLabel}
        isFinished={isFinished}
        needsActivate={needsActivate}
        remainingSeconds={state.remainingSeconds}
        isWrapUpZone={Boolean(state.progress?.is_wrap_up_zone)}
        includeAlgorithm={Boolean(
          data.data && isLiveInterviewSession(data.data) && data.data.configuration?.include_algorithm,
        )}
        canEnd={canReply || mutations.finishMutation.isPending}
        isAlgoPanelOpen={isAlgoPanelOpen}
        headerSubtitle={headerSubtitle}
        onToggleAlgo={() => setIsAlgoPanelOpen((v) => !v)}
        onRequestFinish={() => setters.setShowFinishConfirm(true)}
      />

      {state.error ? <p className="app-error app-live-error">{state.error}</p> : null}

      {needsActivate ? (
        <InterviewLiveStartCard
          isStarting={isStartingInterview}
          showManualStartButton={showManualStartButton}
          sessionId={sessionId}
          onActivate={actions.handleActivate}
        />
      ) : (
        <section className="app-live-layout">
          <InterviewLiveTopicBar currentTopicName={state.progress?.current_topic_name} />
          <InterviewLiveChat
            messages={state.messages}
            showReplyWaiting={showReplyWaiting}
            bottomRef={refs.bottomRef}
          />
          {isFinished ? (
            <div className="app-live-finished">
              <p>{t('live_status_completed')}</p>
              <div className="app-live-start-actions">
                {!reviewMode && state.sessionStatus === 'evaluating' ? (
                  <button
                    type="button"
                    className="app-btn-confirm"
                    onClick={() => navigate('/interviews')}
                  >
                    Records
                  </button>
                ) : null}
                {state.sessionStatus === 'completed' ? (
                  <button
                    type="button"
                    className="app-btn-confirm"
                    onClick={() => navigate(`/interviews/${sessionId}/evaluation`)}
                  >
                    Evaluation
                  </button>
                ) : null}
                <button
                  type="button"
                  className="app-text-button"
                  onClick={() => navigate(`/interviews/${sessionId}/plan`)}
                >
                  {tc('back')}
                </button>
              </div>
            </div>
          ) : (
            <InterviewLiveComposer
              draft={state.draft}
              canReply={canReply}
              onDraftChange={setters.setDraft}
              onSubmit={actions.handleSubmit}
              onKeyDown={handleComposerKeyDown}
            />
          )}
        </section>
      )}

      {isAlgoPanelOpen ? (
        <aside className="app-algo-panel" role="complementary" aria-label={t('algo_title')}>
          <header className="app-algo-panel-head">
            <h3>{t('algo_title')}</h3>
            <button
              type="button"
              className="app-algo-panel-close"
              onClick={() => setIsAlgoPanelOpen(false)}
              aria-label={tc('close')}
            >
              ×
            </button>
          </header>
          <AlgorithmTurn
            token={token}
            problemId={algoResult?.problem_id || 'two_sum'}
            disabled={!canReply}
            onResult={(r) => setAlgoResult({ problem_id: r.problem_id, overall: r.overall })}
          />
        </aside>
      ) : null}

      <ConfirmDialog
        open={state.showFinishConfirm}
        title={t('live_finish_confirm_title')}
        description={t('live_finish_confirm_body')}
        confirmLabel={t('live_end_btn')}
        cancelLabel={t('live_send')}
        loading={mutations.finishMutation.isPending}
        danger
        onConfirm={() => void actions.handleFinishConfirm()}
        onCancel={() => setters.setShowFinishConfirm(false)}
      />

      <LoadingOverlay
        open={state.showEvalGeneratingOverlay}
        message={t('live_eval_overlay')}
        hideLabel
      />
    </div>
  )
}

function formatRemainingTime(seconds: number | null) {
  if (seconds === null) return '—'
  if (seconds <= 0) return '00:00'
  const minutes = Math.floor(seconds / 60)
  const rest = seconds % 60
  return `${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}`
}
