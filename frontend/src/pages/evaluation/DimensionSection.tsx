// D3：各维度评价
import { Card } from '@/components/ui/card'
import { Layers3, Play } from 'lucide-react'
import { useState } from 'react'
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
  const [selectedTopicId, setSelectedTopicId] = useState(competencies[0]?.topic_id ?? '')
  const selectedCompetency =
    competencies.find((item) => item.topic_id === selectedTopicId) ?? competencies[0]

  if (!selectedCompetency) return null

  return (
    <section className="v2-eval-section-wrap v2-eval-dimensions">
      <Card className="v2-panel v2-eval-dimensions-panel">
        <div className="v2-eval-dimensions-panel-head">
          <h3>
            <Layers3 size={18} />
            各维度评价
          </h3>
          <p>各维度以状态和文字点评为主；上方综合分是本页唯一的数值参考。讨论不足的维度未计入综合分。</p>
        </div>

        <div className="v2-eval-dimensions-body">
          <div className="v2-eval-dimension-workspace">
            <div className="v2-eval-dimension-tabs" role="tablist" aria-label="各维度评价">
              {competencies.map((competency, index) => {
                const Icon = DIMENSION_TAB_ICONS[index % DIMENSION_TAB_ICONS.length]
                const active = competency.topic_id === selectedCompetency.topic_id
                const visualTone = resolveCompetencyVisualTone(competency.status, competency.score)
                const statusLabel = resolveCompetencyStatusLabel(competency.status, competency.score)
                return (
                  <button
                    key={competency.topic_id}
                    type="button"
                    role="tab"
                    aria-selected={active}
                    className={`v2-eval-dimension-tab${active ? ' active' : ''}`}
                    onClick={() => setSelectedTopicId(competency.topic_id)}
                  >
                    <Icon size={16} />
                    <span className="v2-eval-dimension-tab-name">{competency.name}</span>
                    <span className={`v2-eval-dimension-tab-status v2-eval-dimension-tab-status-${visualTone}`}>
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
  const evidenceRounds = buildEvidenceRounds(competency)
  const visualTone = resolveCompetencyVisualTone(competency.status, competency.score)
  const comment = competency.evaluation_comment?.trim()

  return (
    <div className="v2-eval-dimension-detail" role="tabpanel" aria-label={`${competency.name}评价详情`}>
      <div className={`v2-eval-dimension-comment-block v2-eval-dimension-comment-block-${visualTone}`}>
        <h4>维度评价</h4>
        <p>{comment || '暂无维度评价。'}</p>
      </div>

      {evidenceRounds.length ? (
        <div className="v2-eval-evidence-section">
          <div className="v2-eval-evidence-section-head">
            <h4>回答依据</h4>
            <p className="v2-eval-evidence-section-note">按对话先后顺序展示该主题下的全部问答。</p>
          </div>
          <ul className="v2-eval-evidence-rounds">
            {evidenceRounds.map((round) => (
              <li key={round.key} className="v2-eval-evidence-round">
                <div className="v2-eval-evidence-round-head">
                  <span className="v2-eval-evidence-round-index">第 {round.index} 轮</span>
                  <button type="button" className="v2-eval-evidence-play" onClick={onReview}>
                    <Play size={14} />
                    回放片段
                  </button>
                </div>
                {round.question ? (
                  <div className="v2-eval-evidence-qa-block">
                    <span className="v2-eval-evidence-qa-label">面试官</span>
                    <p>{round.question}</p>
                  </div>
                ) : null}
                <div className="v2-eval-evidence-qa-block">
                  <span className="v2-eval-evidence-qa-label">你的回答</span>
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
  return <span className={`v2-eval-status-dot v2-eval-status-dot-${tone}`} aria-hidden />
}
