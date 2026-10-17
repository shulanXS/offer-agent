// D3：JD 要点验证
import { Card } from '@/components/ui/card'
import { BriefcaseBusiness } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { EvaluationJdMatch } from '@/types/interviewEvaluation'
import { buildJdMatchListItems, jdStatusLabel } from './utils'

export function JdMatchSection({ jdMatch }: { jdMatch: EvaluationJdMatch }) {
  const { t } = useTranslation('evaluation')
  const items = buildJdMatchListItems(jdMatch)
  const alignedCount = jdMatch.verified_aligned.length
  const riskCount = jdMatch.verified_with_risk.length
  const unverifiedCount = jdMatch.unverified.length

  return (
    <section className="app-eval-section-wrap app-eval-jd">
      <Card className="app-panel app-eval-jd-panel">
        <div className="app-eval-jd-panel-head">
          <h3>
            <BriefcaseBusiness size={18} />
            {t('jd_match_section_title')}
          </h3>
          <p>{jdMatch.summary}</p>
          {items.length ? (
            <div className="app-eval-jd-stats">
              {alignedCount ? (
                <span className="app-eval-jd-stat app-eval-jd-stat-aligned">
                  {t('jd_match_stat_aligned', { count: alignedCount })}
                </span>
              ) : null}
              {riskCount ? (
                <span className="app-eval-jd-stat app-eval-jd-stat-risk">
                  {t('jd_match_stat_risk', { count: riskCount })}
                </span>
              ) : null}
              {unverifiedCount ? (
                <span className="app-eval-jd-stat app-eval-jd-stat-unverified">
                  {t('jd_match_stat_unverified', { count: unverifiedCount })}
                </span>
              ) : null}
            </div>
          ) : null}
          {items.length ? (
            <p className="app-eval-jd-disclaimer">{t('jd_match_disclaimer')}</p>
          ) : null}
        </div>

        <div className="app-eval-jd-body">
          {items.length ? (
            <ul className="app-eval-jd-checklist">
              {items.map((item) => (
                <li
                  key={item.key}
                  className={`app-eval-jd-checklist-item app-eval-jd-checklist-item-${item.status}`}
                >
                  <div className="app-eval-jd-checklist-row">
                    <strong>{item.requirement}</strong>
                    <span className={`app-eval-jd-status-badge app-eval-jd-status-badge-${item.status}`}>
                      {jdStatusLabel(item.status, t)}
                    </span>
                  </div>
                  {item.topic_name ? (
                    <span className="app-eval-jd-topic">
                      {t('jd_match_topic_label')}：{item.topic_name}
                    </span>
                  ) : null}
                  {item.note ? <span className="app-eval-jd-note">{item.note}</span> : null}
                  {item.evidence_quotes?.length ? (
                    <blockquote className="app-eval-jd-quote">{item.evidence_quotes[0]}</blockquote>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="app-eval-empty-copy app-eval-jd-empty-copy">{jdMatch.summary}</p>
          )}
        </div>
      </Card>
    </section>
  )
}
