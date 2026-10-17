// D3：综合得分圆环
import { useTranslation } from 'react-i18next'

export function ScoreRing({ score }: { score: number | null | undefined }) {
  const { t } = useTranslation('records')
  if (score == null) {
    return (
      <div className="app-eval-score-ring empty" aria-label={t('score_empty')}>
        <span className="app-eval-score-empty">—</span>
      </div>
    )
  }

  const progress = Math.max(0, Math.min(100, score))
  // 简单色调：≥80 绿；60-79 蓝；40-59 橙；<40 红
  const tone = progress >= 80 ? 'high' : progress >= 60 ? 'mid' : progress >= 40 ? 'low' : 'critical'

  return (
    <div className={`app-eval-score-ring app-eval-score-ring-${tone}`} aria-hidden>
      <svg viewBox="0 0 36 36" className="app-eval-score-svg" aria-hidden>
        <path
          className="app-eval-score-track"
          d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
        />
        <path
          className="app-eval-score-progress"
          strokeDasharray={`${progress}, 100`}
          d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
        />
      </svg>
      <div className="app-eval-score-center">
        <strong>{score}</strong>
      </div>
    </div>
  )
}
