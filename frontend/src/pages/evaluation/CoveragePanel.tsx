// D3：考察覆盖面板
import { useTranslation } from 'react-i18next'
import type { EvaluationCompetency } from '@/types/interviewEvaluation'
import { coverageBarWidth, coverageLabel, resolveOverviewCoverageStatus } from './utils'

export function CoveragePanel({
  competencies,
  total,
  scored,
}: {
  competencies: EvaluationCompetency[]
  total: number
  scored: number
}) {
  const { t } = useTranslation('evaluation')
  return (
    <div className="app-eval-overview-coverage">
      <div className="app-eval-overview-coverage-head">
        <p className="app-eval-overview-label">{t('coverage_title')}</p>
        <span>
          {t('coverage_topics_total', { total: total || competencies.length })} · {t('coverage_topics_scored', { scored })}
        </span>
      </div>
      <ul className="app-eval-overview-coverage-list">
        {competencies.map((competency) => {
          const status = resolveOverviewCoverageStatus(competency)
          return (
            <li key={competency.topic_id}>
              <span className="app-eval-overview-coverage-name">{competency.name}</span>
              <div className="app-eval-overview-coverage-bar-wrap">
                <div
                  className={`app-eval-overview-coverage-bar app-eval-overview-coverage-bar-${status}`}
                  style={{ width: `${coverageBarWidth(status)}%` }}
                />
              </div>
              <span className={`app-eval-overview-coverage-status app-eval-overview-coverage-status-${status}`}>
                {coverageLabel(status, t)}
              </span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
