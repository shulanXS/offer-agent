// D3：综合得分圆环
export function ScoreRing({ score }: { score: number | null | undefined }) {
  if (score == null) {
    return (
      <div className="v2-eval-score-ring empty" aria-label="暂无评分">
        <span className="v2-eval-score-empty">—</span>
      </div>
    )
  }

  const progress = Math.max(0, Math.min(100, score))
  // 简单色调：≥80 绿；60-79 蓝；40-59 橙；<40 红
  const tone = progress >= 80 ? 'high' : progress >= 60 ? 'mid' : progress >= 40 ? 'low' : 'critical'

  return (
    <div className={`v2-eval-score-ring v2-eval-score-ring-${tone}`} aria-hidden>
      <svg viewBox="0 0 36 36" className="v2-eval-score-svg" aria-hidden>
        <path
          className="v2-eval-score-track"
          d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
        />
        <path
          className="v2-eval-score-progress"
          strokeDasharray={`${progress}, 100`}
          d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
        />
      </svg>
      <div className="v2-eval-score-center">
        <strong>{score}</strong>
      </div>
    </div>
  )
}
