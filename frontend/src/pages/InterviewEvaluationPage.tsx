// D3：评估页 - 重构后主入口
// 业务逻辑（load/error/refresh）+ 顶层布局
// 子组件在同目录中按职责拆分
import { InterviewHeaderArt } from '@/components/InterviewHeaderArt'
import { Card } from '@/components/ui/card'
import { useInterviewEvaluationReport, useRetryInterviewEvaluation } from '@/hooks/useInterviewEvaluation'
import { useInterviewLearningContext } from '@/hooks/useInterviewLearning'
import { ChevronLeft, LoaderCircle } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'
import { CoveragePanel } from './evaluation/CoveragePanel'
import { DegradedBanner } from './evaluation/DegradedBanner'
import { DimensionSection } from './evaluation/DimensionSection'
import { FeedbackSection } from './evaluation/FeedbackSection'
import { JdMatchSection } from './evaluation/JdMatchSection'
import { PracticeSection } from './evaluation/PracticeSection'
import { ScoreRing } from './evaluation/ScoreRing'
import { SessionComparisonSection } from './evaluation/SessionComparisonSection'
import { buildScorePresentation } from './evaluation/utils'
import i18n from '@/i18n'
import { buildUnifiedPracticeCards, shouldShowCrossSessionComparison } from '@/utils/buildUnifiedPracticeCards'
import type { InterviewEvaluationReport } from '@/types/interviewEvaluation'

interface InterviewEvaluationPageProps {
  token: string
}

export function InterviewEvaluationPage({ token }: InterviewEvaluationPageProps) {
  const { t } = useTranslation('evaluation')
  const { t: tc } = useTranslation('common')
  const { sessionId = '' } = useParams()
  const navigate = useNavigate()
  const { data, isPending, error, refetch } = useInterviewEvaluationReport(token, sessionId)
  const retryMutation = useRetryInterviewEvaluation(token, sessionId)

  const report = data?.evaluation ?? null
  const isGenerating = (isPending || retryMutation.isPending) && !report
  const [retryHint, setRetryHint] = useState('')

  async function handleRetry() {
    setRetryHint('')
    try {
      await retryMutation.mutateAsync()
    } catch {
      setRetryHint(tc('retry'))
      await refetch()
    }
  }

  return (
    <div className="v2-eval-page">
      <header className="v2-page-header v2-eval-header">
        <div>
          <button type="button" className="v2-eval-back-link" onClick={() => navigate('/interviews')}>
            <ChevronLeft size={16} />
            {t('btn_back')}
          </button>
          <h2>{t('title')}</h2>
          <p>{t('section_overview')}</p>
        </div>
        <InterviewHeaderArt />
      </header>

      {isGenerating ? (
        <Card className="v2-panel v2-eval-loading">
          <LoaderCircle className="v2-eval-spinner" size={28} />
          <h3>{t('loading')}</h3>
          <p>{t('section_overview')}</p>
        </Card>
      ) : null}

      {!isGenerating && error ? (
        <Card className="v2-panel v2-eval-error">
          <h3>{t('degraded_banner_title')}</h3>
          <p className="v2-error">{readError(error)}</p>
          <div className="v2-eval-actions">
            <button
              type="button"
              className="v2-btn-confirm"
              disabled={retryMutation.isPending}
              onClick={() => void handleRetry()}
            >
              {tc('retry')}
            </button>
          </div>
        </Card>
      ) : null}

      {!isGenerating && !error && report ? (
        <EvaluationReportView
          token={token}
          report={report}
          sessionId={sessionId}
          onReview={() => navigate(`/interviews/${sessionId}/live?review=1`)}
        />
      ) : null}

      {!isGenerating && !error && !report ? (
        <Card className="v2-panel v2-eval-error">
          <h3>—</h3>
          <p>{retryHint || '—'}</p>
          <button
            type="button"
            className="v2-btn-confirm"
            onClick={() => navigate(`/interviews/${sessionId}/live`)}
          >
            {tc('back')}
          </button>
        </Card>
      ) : null}
    </div>
  )
}

function EvaluationReportView({
  token,
  report,
  sessionId,
  onReview,
}: {
  token: string
  report: InterviewEvaluationReport
  sessionId: string
  onReview: () => void
}) {
  const { t } = useTranslation('evaluation')
  const navigate = useNavigate()
  const { data: learningContext } = useInterviewLearningContext(token, sessionId, Boolean(report))
  const candidateReview = report.candidate_review
  const competencies = report.competencies ?? []
  const jdMatch = report.jd_match ?? null
  const scorePresentation = buildScorePresentation(report)
  const highlights = candidateReview?.highlights ?? []
  const weaknesses = candidateReview?.weaknesses ?? []
  const practiceCards = buildUnifiedPracticeCards(report, learningContext)
  const showCrossSession = shouldShowCrossSessionComparison(learningContext)

  return (
    <>
      {scorePresentation.degraded ? <DegradedBanner presentation={scorePresentation} /> : null}

      <section className="v2-eval-section-wrap v2-eval-overview-section">
        <Card className="v2-panel v2-eval-overview-card">
          {scorePresentation.coverageNote ? (
            <p className={`v2-eval-coverage-note v2-eval-overview-top-note${scorePresentation.isPartial ? ' partial' : ''}`}>
              {scorePresentation.coverageNote}
            </p>
          ) : null}

          <div className="v2-eval-overview-grid">
            <div className="v2-eval-overview-score">
              <ScoreRing score={report.overall_score} />
              <p className="v2-eval-overview-score-label">{scorePresentation.scoreLabel}</p>
            </div>

            <div className="v2-eval-overview-summary">
              <p className="v2-eval-overview-label">{t('section_overview')}</p>
              <p className="v2-eval-overview-copy">{candidateReview?.summary}</p>
              {scorePresentation.total > 0 ? (
                <span className="v2-eval-overview-badge">
                  {t('coverage_topics_total', { total: scorePresentation.total })} ·{' '}
                  {t('coverage_topics_scored', { scored: scorePresentation.scored })}
                </span>
              ) : null}
            </div>

            {competencies.length ? (
              <CoveragePanel
                competencies={competencies}
                total={scorePresentation.total}
                scored={scorePresentation.scored}
              />
            ) : null}
          </div>
        </Card>
      </section>

      <FeedbackSection highlights={highlights} weaknesses={weaknesses} />

      {showCrossSession && learningContext ? (
        <SessionComparisonSection context={learningContext} />
      ) : null}
      {practiceCards.length ? (
        <PracticeSection
          cards={practiceCards}
          onPractice={(focusTopic) =>
            navigate('/interviews/new', { state: { prefilledFocusTopics: [focusTopic] } })
          }
        />
      ) : null}

      {competencies.length ? (
        <DimensionSection
          key={sessionId}
          competencies={competencies}
          onReview={onReview}
        />
      ) : null}

      {jdMatch ? <JdMatchSection jdMatch={jdMatch} /> : null}

      <p className="v2-eval-footnote">Session ID: {sessionId}</p>
    </>
  )
}

function readError(error: unknown): string {
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
