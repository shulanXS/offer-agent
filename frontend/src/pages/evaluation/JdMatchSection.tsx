// D3：JD 要点验证
import { Card } from '@/components/ui/card'
import { BriefcaseBusiness } from 'lucide-react'
import type { EvaluationJdMatch } from '@/types/interviewEvaluation'
import { buildJdMatchListItems, jdStatusLabel } from './utils'

export function JdMatchSection({ jdMatch }: { jdMatch: EvaluationJdMatch }) {
  const items = buildJdMatchListItems(jdMatch)
  const alignedCount = jdMatch.verified_aligned.length
  const riskCount = jdMatch.verified_with_risk.length
  const unverifiedCount = jdMatch.unverified.length

  return (
    <section className="v2-eval-section-wrap v2-eval-jd">
      <Card className="v2-panel v2-eval-jd-panel">
        <div className="v2-eval-jd-panel-head">
          <h3>
            <BriefcaseBusiness size={18} />
            本场 JD 要点验证
          </h3>
          <p>{jdMatch.summary}</p>
          {items.length ? (
            <div className="v2-eval-jd-stats">
              {alignedCount ? (
                <span className="v2-eval-jd-stat v2-eval-jd-stat-aligned">已验证 {alignedCount}</span>
              ) : null}
              {riskCount ? (
                <span className="v2-eval-jd-stat v2-eval-jd-stat-risk">有风险 {riskCount}</span>
              ) : null}
              {unverifiedCount ? (
                <span className="v2-eval-jd-stat v2-eval-jd-stat-unverified">
                  尚未验证 {unverifiedCount}
                </span>
              ) : null}
            </div>
          ) : null}
          {items.length ? (
            <p className="v2-eval-jd-disclaimer">
              下列为本场计划对齐的 JD 要点。尚未验证表示本场未充分讨论或证据不足，不代表不符合岗位要求。
            </p>
          ) : null}
        </div>

        <div className="v2-eval-jd-body">
          {items.length ? (
            <ul className="v2-eval-jd-checklist">
              {items.map((item) => (
                <li
                  key={item.key}
                  className={`v2-eval-jd-checklist-item v2-eval-jd-checklist-item-${item.status}`}
                >
                  <div className="v2-eval-jd-checklist-row">
                    <strong>{item.requirement}</strong>
                    <span className={`v2-eval-jd-status-badge v2-eval-jd-status-badge-${item.status}`}>
                      {jdStatusLabel(item.status)}
                    </span>
                  </div>
                  {item.topic_name ? (
                    <span className="v2-eval-jd-topic">关联主题：{item.topic_name}</span>
                  ) : null}
                  {item.note ? <span className="v2-eval-jd-note">{item.note}</span> : null}
                  {item.evidence_quotes?.length ? (
                    <blockquote className="v2-eval-jd-quote">{item.evidence_quotes[0]}</blockquote>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="v2-eval-empty-copy v2-eval-jd-empty-copy">{jdMatch.summary}</p>
          )}
        </div>
      </Card>
    </section>
  )
}
