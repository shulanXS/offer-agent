// D3：考察覆盖面板
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
  return (
    <div className="v2-eval-overview-coverage">
      <div className="v2-eval-overview-coverage-head">
        <p className="v2-eval-overview-label">考察覆盖</p>
        <span>
          计划 {total || competencies.length} 个方向 · 已评 {scored} 个
        </span>
      </div>
      <ul className="v2-eval-overview-coverage-list">
        {competencies.map((competency) => {
          const status = resolveOverviewCoverageStatus(competency)
          return (
            <li key={competency.topic_id}>
              <span className="v2-eval-overview-coverage-name">{competency.name}</span>
              <div className="v2-eval-overview-coverage-bar-wrap">
                <div
                  className={`v2-eval-overview-coverage-bar v2-eval-overview-coverage-bar-${status}`}
                  style={{ width: `${coverageBarWidth(status)}%` }}
                />
              </div>
              <span className={`v2-eval-overview-coverage-status v2-eval-overview-coverage-status-${status}`}>
                {coverageLabel(status)}
              </span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
