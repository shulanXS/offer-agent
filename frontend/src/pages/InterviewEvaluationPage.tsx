// D3：评估页 - 重构后主入口
// 业务逻辑（load/error/refresh）+ 顶层布局
// 子组件在同目录中按职责拆分
import { InterviewHeaderArt } from '@/components/InterviewHeaderArt'
import { Card } from '@/components/ui/card'
import { useInterviewEvaluationReport, useRetryInterviewEvaluation } from '@/hooks/useInterviewEvaluation'
import { useInterviewLearningContext } from '@/hooks/useInterviewLearning'
import { ChevronLeft, LoaderCircle } from 'lucide-react'
import { useState } from 'react'
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
import type { LearningContextResponse } from '@/types/interviewLearning'
import { buildUnifiedPracticeCards, shouldShowCrossSessionComparison } from '@/utils/buildUnifiedPracticeCards'
import type { InterviewEvaluationReport } from '@/types/interviewEvaluation'

interface InterviewEvaluationPageProps {
  token: string
}

export function InterviewEvaluationPage({ token }: InterviewEvaluationPageProps) {
  const { sessionId = '' } = useParams()
  const navigate = useNavigate()
  const { data, isPending, error, refetch } = useInterviewEvaluationReport(token, sessionId)
  const retryMutation = useRetryInterviewEvaluation(token, sessionId)

  const report = data?.evaluation ?? null
  const isGenerating = (isPending || retryMutation.isPending) && !report

  async function handleRetry() {
    try {
      await retryMutation.mutateAsync()
    } catch {
      await refetch()
    }
  }

  return (
    <div className="v2-eval-page">
      <header className="v2-page-header v2-eval-header">
        <div>
          <button type="button" className="v2-eval-back-link" onClick={() => navigate('/interviews')}>
            <ChevronLeft size={16} />
            返回面试记录
          </button>
          <h2>面试评估</h2>
          <p>基于本场对话整理的可读复盘，帮你了解表现与主要不足。</p>
        </div>
        <InterviewHeaderArt />
      </header>

      {isGenerating ? (
        <Card className="v2-panel v2-eval-loading">
          <LoaderCircle className="v2-eval-spinner" size={28} />
          <h3>正在生成面试反馈</h3>
          <p>系统正在整理总结与各维度评价，请稍候。</p>
        </Card>
      ) : null}

      {!isGenerating && error ? (
        <Card className="v2-panel v2-eval-error">
          <h3>评估生成失败</h3>
          <p className="v2-error">{readError(error)}</p>
          <div className="v2-eval-actions">
            <button
              type="button"
              className="v2-btn-confirm"
              disabled={retryMutation.isPending}
              onClick={() => void handleRetry()}
            >
              重试评估
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
          <h3>暂无可展示的评估结果</h3>
          <p>请先完成面试并进入评估状态。</p>
          <button
            type="button"
            className="v2-btn-confirm"
            onClick={() => navigate(`/interviews/${sessionId}/live`)}
          >
            返回面试
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
              <p className="v2-eval-overview-label">综合评价</p>
              <p className="v2-eval-overview-copy">{candidateReview?.summary}</p>
              {scorePresentation.total > 0 ? (
                <span className="v2-eval-overview-badge">
                  计划 {scorePresentation.total} 个方向 · 已评 {scorePresentation.scored} 个
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

      <p className="v2-eval-footnote">会话 ID：{sessionId}</p>
    </>
  )
}

function readError(error: unknown): string {
  return error instanceof Error ? error.message : '请求失败'
}
