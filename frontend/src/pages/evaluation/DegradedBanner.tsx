// D3：评估降级提示（B1 配套）
import type { ScorePresentation } from '../evaluation/utils'

export function DegradedBanner({ presentation }: { presentation: ScorePresentation }) {
  if (!presentation.degraded) return null
  return (
    <section className="v2-eval-zone">
      <div className="v2-eval-degraded-banner" role="alert">
        <strong>评估采用降级路径</strong>
        <p>{presentation.degradedMessage || '本场评估来自降级模板，建议重新面试或联系管理员。'}</p>
        {presentation.degradedReason ? (
          <p className="v2-eval-degraded-reason">原因：{presentation.degradedReason}</p>
        ) : null}
      </div>
    </section>
  )
}
