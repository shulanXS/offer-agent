// D3：本次反馈（亮点 / 不足）
import { Card } from '@/components/ui/card'
import { AlertTriangle, ThumbsUp } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import type { EvaluationFeedbackEntry } from '@/types/interviewEvaluation'
import {
  HIGHLIGHT_ITEM_ICONS,
  WEAKNESS_ITEM_ICONS,
  normalizeFeedbackEntry,
} from './utils'

export function FeedbackSection({
  highlights,
  weaknesses,
}: {
  highlights: EvaluationFeedbackEntry[]
  weaknesses: EvaluationFeedbackEntry[]
}) {
  const { t } = useTranslation('evaluation')
  return (
    <section className="v2-eval-zone v2-eval-session-feedback-zone">
      <Card className="v2-panel v2-eval-session-feedback-panel">
        <div className="v2-eval-session-feedback-panel-head">
          <h3>{t('feedback_title')}</h3>
          <p>{t('section_overview')}</p>
        </div>
        <div className="v2-eval-session-feedback-columns">
          <Column
            icon={<ThumbsUp size={18} />}
            title={t('section_strengths')}
            items={highlights}
            empty="—"
            tone="highlight"
            itemIcons={HIGHLIGHT_ITEM_ICONS}
          />
          <Column
            icon={<AlertTriangle size={18} />}
            title={t('section_risks')}
            items={weaknesses}
            empty="—"
            tone="weakness"
            itemIcons={WEAKNESS_ITEM_ICONS}
          />
        </div>
      </Card>
    </section>
  )
}

function Column({
  icon,
  title,
  items,
  empty,
  tone,
  itemIcons,
}: {
  icon: ReactNode
  title: string
  items: EvaluationFeedbackEntry[]
  empty: string
  tone: 'highlight' | 'weakness'
  itemIcons: readonly LucideIcon[]
}) {
  return (
    <div className={`v2-eval-session-feedback-column v2-eval-session-feedback-${tone}`}>
      <div className="v2-eval-session-feedback-column-head">
        <span
          className={`v2-eval-session-feedback-column-icon v2-eval-session-feedback-column-icon-${tone}`}
          aria-hidden
        >
          {icon}
        </span>
        <h4>{title}</h4>
      </div>
      <FeedbackList items={items} empty={empty} tone={tone} itemIcons={itemIcons} />
    </div>
  )
}

function FeedbackList({
  items,
  empty,
  tone,
  itemIcons,
}: {
  items: EvaluationFeedbackEntry[]
  empty: string
  tone: 'highlight' | 'weakness'
  itemIcons: readonly LucideIcon[]
}) {
  if (!items.length) return <p className="v2-eval-empty-copy">{empty}</p>
  return (
    <ul className="v2-eval-feedback-detail-list">
      {items.map((item, index) => {
        const parsed = normalizeFeedbackEntry(item)
        const ItemIcon = itemIcons[index % itemIcons.length]
        return (
          <li
            key={`${parsed.title}-${index}`}
            className={`v2-eval-feedback-detail-item v2-eval-feedback-detail-item-${tone}`}
          >
            <span
              className={`v2-eval-feedback-detail-topic-icon v2-eval-feedback-detail-topic-icon-${tone}`}
              aria-hidden
            >
              <ItemIcon size={18} />
            </span>
            <div className="v2-eval-feedback-detail-copy">
              <strong>{parsed.title}</strong>
              <p>{parsed.body}</p>
            </div>
          </li>
        )
      })}
    </ul>
  )
}
