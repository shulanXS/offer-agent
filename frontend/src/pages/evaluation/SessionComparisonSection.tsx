// D3：跨场次对比
import { Card } from '@/components/ui/card'
import { Minus, TrendingDown, TrendingUp } from 'lucide-react'
import type { LearningContextResponse } from '@/types/interviewLearning'
import type { InterviewEvaluationReport } from '@/types/interviewEvaluation'

export function SessionComparisonSection({
  context,
  currentReport,
}: {
  context: LearningContextResponse
  currentReport?: InterviewEvaluationReport | null
}) {
  const comparison = context.session_comparison
  const previousOverallScore = context.previous_overall_score
  const currentOverallScore = currentReport?.overall_score ?? null
  const hasScoreComparison =
    previousOverallScore != null && currentOverallScore != null

  if (!comparison?.points.length && !hasScoreComparison) return null

  const coverage = comparison?.discussed_coverage
  const summaryTag = comparison ? formatComparisonSummaryTag(comparison.summary_line) : ''
  const summaryTone = comparison
    ? deriveComparisonSummaryTone(comparison)
    : 'same'

  return (
    <section className="v2-eval-zone">
      <Card className="v2-panel v2-eval-cross-session-panel">
        <div className="v2-eval-cross-session-panel-head">
          <div className="v2-eval-cross-session-panel-head-row">
            <h3>与上一场对比</h3>
            {summaryTag ? (
              <span className={`v2-eval-cross-session-head-tag v2-eval-cross-session-head-tag-${summaryTone}`}>
                {summaryTag}
              </span>
            ) : null}
          </div>
          <p>
            已模拟 {context.session_count} 场 · {context.target_role_label || context.target_role} ·{' '}
            {context.interview_type_label || context.interview_type}
            。对比基于你的历史模拟，不影响本场评分。
          </p>
        </div>

        <div className="v2-eval-cross-session-body">
          <div className="v2-eval-cross-session-layout">
            {hasScoreComparison ? (
              <div className="v2-eval-cross-session-coverage-panel">
                <p className="v2-eval-cross-session-panel-title">总分对比</p>
                <ScoreComparisonRow
                  previousScore={previousOverallScore!}
                  currentScore={currentOverallScore!}
                />
              </div>
            ) : null}
            {comparison?.points.length ? (
              <div className="v2-eval-cross-session-coverage-panel">
                <p className="v2-eval-cross-session-panel-title">{coverage?.label || '已考察方向'}</p>
                <div className="v2-eval-cross-session-coverage-compare">
                  <div className="v2-eval-cross-session-coverage-side">
                    <span className="v2-eval-cross-session-coverage-label">上一场</span>
                    <strong className="v2-eval-cross-session-coverage-value">
                      {coverage?.baseline_count ?? 0}
                    </strong>
                    <span className="v2-eval-cross-session-coverage-unit">个</span>
                  </div>
                  <div className="v2-eval-cross-session-coverage-ring" aria-hidden="true">
                    <TrendingUp size={22} />
                  </div>
                  <div className="v2-eval-cross-session-coverage-side current">
                    <span className="v2-eval-cross-session-coverage-label">本场</span>
                    <strong className="v2-eval-cross-session-coverage-value">
                      {coverage?.current_count ?? 0}
                    </strong>
                    <span className="v2-eval-cross-session-coverage-unit">个</span>
                  </div>
                </div>
              </div>
            ) : null}

            {comparison?.points.length ? (
              <div className="v2-eval-cross-session-changes-panel">
                <ul className="v2-eval-cross-session-change-list">
                  {comparison.points.map((point) => (
                    <li
                      key={`${point.category}-${point.headline}`}
                      className={`v2-eval-cross-session-change-item v2-eval-cross-session-change-item-${point.tone}`}
                    >
                      <div className="v2-eval-cross-session-change-icon">
                        {point.tone === 'better' ? (
                          <TrendingUp size={16} />
                        ) : point.tone === 'worse' ? (
                          <TrendingDown size={16} />
                        ) : (
                          <Minus size={16} />
                        )}
                      </div>
                      <span className="v2-eval-cross-session-change-line">
                        {formatComparisonPointLine(point)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        </div>
      </Card>
    </section>
  )
}

function ScoreComparisonRow({
  previousScore,
  currentScore,
}: {
  previousScore: number
  currentScore: number
}) {
  const delta = Math.round(currentScore - previousScore)
  const tone: 'better' | 'worse' | 'same' =
    delta > 0 ? 'better' : delta < 0 ? 'worse' : 'same'
  const verb = tone === 'better' ? '提升' : tone === 'worse' ? '下降' : '持平'
  return (
    <div className="v2-eval-cross-session-coverage-compare">
      <div className="v2-eval-cross-session-coverage-side">
        <span className="v2-eval-cross-session-coverage-label">上一场</span>
        <strong className="v2-eval-cross-session-coverage-value">{previousScore}</strong>
        <span className="v2-eval-cross-session-coverage-unit">分</span>
      </div>
      <div className="v2-eval-cross-session-coverage-ring" aria-hidden="true">
        {tone === 'better' ? (
          <TrendingUp size={22} />
        ) : tone === 'worse' ? (
          <TrendingDown size={22} />
        ) : (
          <Minus size={22} />
        )}
      </div>
      <div className="v2-eval-cross-session-coverage-side current">
        <span className="v2-eval-cross-session-coverage-label">本场</span>
        <strong className="v2-eval-cross-session-coverage-value">{currentScore}</strong>
        <span className="v2-eval-cross-session-coverage-unit">分</span>
      </div>
      <span
        className={`v2-eval-cross-session-head-tag v2-eval-cross-session-head-tag-${tone}`}
        aria-label={`${verb} ${Math.abs(delta)} 分`}
      >
        {tone === 'same' ? verb : `${verb} ${Math.abs(delta)} 分`}
      </span>
    </div>
  )
}

function formatComparisonSummaryTag(summaryLine: string | undefined): string {
  if (!summaryLine?.trim()) return ''
  return summaryLine.replace(/^相比上场[：:]\s*/, '').trim()
}

function deriveComparisonSummaryTone(comparison: { points: { tone: string }[] }): string {
  const actionable = comparison.points.filter(
    (point) => point.tone === 'better' || point.tone === 'worse',
  )
  if (!actionable.length) return 'same'
  const hasBetter = actionable.some((point) => point.tone === 'better')
  const hasWorse = actionable.some((point) => point.tone === 'worse')
  if (hasBetter && hasWorse) return 'same'
  return hasBetter ? 'better' : 'worse'
}

function formatComparisonPointLine(point: { headline: string; detail?: string }): string {
  const headline = point.headline.trim()
  const detail = point.detail?.trim()
  return detail ? `${headline}，${detail}` : headline
}
