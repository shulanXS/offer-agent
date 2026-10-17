// D3：各维度评价
import { Card } from '@/components/ui/card'
import { Layers3, Play } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { EvaluationCompetency, EvaluationCompetencyStatus } from '@/types/interviewEvaluation'
import { resolveCompetencyStatusLabel, resolveCompetencyVisualTone } from '@/utils/evaluationScorePresentation'
import { DIMENSION_TAB_ICONS, buildEvidenceRounds } from './utils'

export function DimensionSection({
  competencies,
  onReview,
}: {
  competencies: EvaluationCompetency[]
  onReview: () => void
}) {
  const { t } = useTranslation('evaluation')
  const [selectedTopicId, setSelectedTopicId] = useState(competencies[0]?.topic_id ?? '')
  const selectedCompetency =
    competencies.find((item) => item.topic_id === selectedTopicId) ?? competencies[0]

  if (!selectedCompetency) return null

  return (
    <section className="app-eval-section-wrap app-eval-dimensions">
      <Card className="app-panel app-eval-dimensions-panel">
        <div className="app-eval-dimensions-panel-head">
          <h3>
            <Layers3 size={18} />
            {t('dimension_title_section')}
          </h3>
          <p>{t('dimension_section_subtitle')}</p>
        </div>

        <div className="app-eval-dimensions-body">
          <div className="app-eval-dimension-workspace">
            <div className="app-eval-dimension-tabs" role="tablist" aria-label={t('dimension_title_section')}>
              {competencies.map((competency, index) => {
                const Icon = DIMENSION_TAB_ICONS[index % DIMENSION_TAB_ICONS.length]
                const active = competency.topic_id === selectedCompetency.topic_id
                const visualTone = resolveCompetencyVisualTone(competency.status, competency.score)
                const statusLabel = resolveCompetencyStatusLabel(competency.status, competency.score, t)
                return (
                  <button
                    key={competency.topic_id}
                    type="button"
                    role="tab"
                    aria-selected={active}
                    className={`app-eval-dimension-tab${active ? ' active' : ''}`}
                    onClick={() => setSelectedTopicId(competency.topic_id)}
                  >
                    <Icon size={16} />
                    <span className="app-eval-dimension-tab-name">{competency.name}</span>
                    <span className={`app-eval-dimension-tab-status app-eval-dimension-tab-status-${visualTone}`}>
                      <StatusDot status={competency.status} score={competency.score} />
                      {statusLabel}
                    </span>
                  </button>
                )
              })}
            </div>

            <DimensionDetailPanel competency={selectedCompetency} onReview={onReview} />
          </div>
        </div>
      </Card>
    </section>
  )
}

function DimensionDetailPanel({
  competency,
  onReview,
}: {
  competency: EvaluationCompetency
  onReview: () => void
}) {
  const { t } = useTranslation('evaluation')
  const evidenceRounds = buildEvidenceRounds(competency)
  const visualTone = resolveCompetencyVisualTone(competency.status, competency.score)
  const comment = competency.evaluation_comment?.trim()

  return (
    <div className="app-eval-dimension-detail" role="tabpanel" aria-label={t('dimension_detail_aria', { name: competency.name })}>
      <div className={`app-eval-dimension-comment-block app-eval-dimension-comment-block-${visualTone}`}>
        <h4>{t('dimension_comment_title')}</h4>
        <p>{comment || t('dimension_no_comment')}</p>
      </div>

      {evidenceRounds.length ? (
        <div className="app-eval-evidence-section">
          <div className="app-eval-evidence-section-head">
            <h4>{t('evidence_section_title')}</h4>
            <p className="app-eval-evidence-section-note">{t('evidence_section_note')}</p>
          </div>
          <ul className="app-eval-evidence-rounds">
            {evidenceRounds.map((round) => (
              <li key={round.key} className="app-eval-evidence-round">
                <div className="app-eval-evidence-round-head">
                  <span className="app-eval-evidence-round-index">{t('evidence_round_label', { n: round.index })}</span>
                  <button type="button" className="app-eval-evidence-play" onClick={onReview}>
                    <Play size={14} />
                    {t('evidence_replay_btn')}
                  </button>
                </div>
                {round.question ? (
                  <div className="app-eval-evidence-qa-block">
                    <span className="app-eval-evidence-qa-label">{t('evidence_label_interviewer')}</span>
                    <p>{round.question}</p>
                  </div>
                ) : null}
                <div className="app-eval-evidence-qa-block">
                  <span className="app-eval-evidence-qa-label">{t('evidence_label_candidate')}</span>
                  <p>{round.answer}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  )
}

function StatusDot({
  status,
  score,
}: {
  status: EvaluationCompetencyStatus
  score?: number | null
}) {
  const tone = resolveCompetencyVisualTone(status, score)
  return <span className={`app-eval-status-dot app-eval-status-dot-${tone}`} aria-hidden />
}
