// D3：跨场次对比
import { Card } from '@/components/ui/card'
import { Minus, TrendingDown, TrendingUp } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { LearningContextResponse } from '@/types/interviewLearning'
import type { InterviewEvaluationReport } from '@/types/interviewEvaluation'

export function SessionComparisonSection({
  context,
  currentReport,
}: {
  context: LearningContextResponse
  currentReport?: InterviewEvaluationReport | null
}) {
  const { t } = useTranslation('evaluation')
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
    <section className="app-eval-zone">
      <Card className="app-panel app-eval-cross-session-panel">
        <div className="app-eval-cross-session-panel-head">
          <div className="app-eval-cross-session-panel-head-row">
            <h3>{t('comparison_title')}</h3>
            {summaryTag ? (
              <span className={`app-eval-cross-session-head-tag app-eval-cross-session-head-tag-${summaryTone}`}>
                {summaryTag}
              </span>
            ) : null}
          </div>
          <p>
            {t('comparison_summary_intro', {
              count: context.session_count,
              role: context.target_role_label || context.target_role,
              type: context.interview_type_label || context.interview_type,
            })}
          </p>
        </div>

        <div className="app-eval-cross-session-body">
          <div className="app-eval-cross-session-layout">
            {hasScoreComparison ? (
              <div className="app-eval-cross-session-coverage-panel">
                <p className="app-eval-cross-session-panel-title">{t('comparison_score_label')}</p>
                <ScoreComparisonRow
                  previousScore={previousOverallScore!}
                  currentScore={currentOverallScore!}
                />
              </div>
            ) : null}
            {comparison?.points.length ? (
              <div className="app-eval-cross-session-coverage-panel">
                <p className="app-eval-cross-session-panel-title">{coverage?.label || t('comparison_coverage_fallback')}</p>
                <div className="app-eval-cross-session-coverage-compare">
                  <div className="app-eval-cross-session-coverage-side">
                    <span className="app-eval-cross-session-coverage-label">{t('comparison_previous')}</span>
                    <strong className="app-eval-cross-session-coverage-value">
                      {coverage?.baseline_count ?? 0}
                    </strong>
                    <span className="app-eval-cross-session-coverage-unit">{t('comparison_unit_topic')}</span>
                  </div>
                  <div className="app-eval-cross-session-coverage-ring" aria-hidden="true">
                    <TrendingUp size={22} />
                  </div>
                  <div className="app-eval-cross-session-coverage-side current">
                    <span className="app-eval-cross-session-coverage-label">{t('comparison_current')}</span>
                    <strong className="app-eval-cross-session-coverage-value">
                      {coverage?.current_count ?? 0}
                    </strong>
                    <span className="app-eval-cross-session-coverage-unit">{t('comparison_unit_topic')}</span>
                  </div>
                </div>
              </div>
            ) : null}

            {comparison?.points.length ? (
              <div className="app-eval-cross-session-changes-panel">
                <ul className="app-eval-cross-session-change-list">
                  {comparison.points.map((point) => (
                    <li
                      key={`${point.category}-${point.headline}`}
                      className={`app-eval-cross-session-change-item app-eval-cross-session-change-item-${point.tone}`}
                    >
                      <div className="app-eval-cross-session-change-icon">
                        {point.tone === 'better' ? (
                          <TrendingUp size={16} />
                        ) : point.tone === 'worse' ? (
                          <TrendingDown size={16} />
                        ) : (
                          <Minus size={16} />
                        )}
                      </div>
                      <span className="app-eval-cross-session-change-line">
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
  const { t } = useTranslation('evaluation')
  const delta = Math.round(currentScore - previousScore)
  const tone: 'better' | 'worse' | 'same' =
    delta > 0 ? 'better' : delta < 0 ? 'worse' : 'same'
  const verbKey = tone === 'better' ? 'comparison_verb_better' : tone === 'worse' ? 'comparison_verb_worse' : 'comparison_verb_same'
  const verb = t(verbKey)
  return (
    <div className="app-eval-cross-session-coverage-compare">
      <div className="app-eval-cross-session-coverage-side">
        <span className="app-eval-cross-session-coverage-label">{t('comparison_previous')}</span>
        <strong className="app-eval-cross-session-coverage-value">{previousScore}</strong>
        <span className="app-eval-cross-session-coverage-unit">{t('comparison_unit_score')}</span>
      </div>
      <div className="app-eval-cross-session-coverage-ring" aria-hidden="true">
        {tone === 'better' ? (
          <TrendingUp size={22} />
        ) : tone === 'worse' ? (
          <TrendingDown size={22} />
        ) : (
          <Minus size={22} />
        )}
      </div>
      <div className="app-eval-cross-session-coverage-side current">
        <span className="app-eval-cross-session-coverage-label">{t('comparison_current')}</span>
        <strong className="app-eval-cross-session-coverage-value">{currentScore}</strong>
        <span className="app-eval-cross-session-coverage-unit">{t('comparison_unit_score')}</span>
      </div>
      <span
        className={`app-eval-cross-session-head-tag app-eval-cross-session-head-tag-${tone}`}
        aria-label={t('comparison_delta_aria', { verb, count: Math.abs(delta) })}
      >
        {tone === 'same' ? verb : t('comparison_delta_text', { verb, count: Math.abs(delta) })}
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
