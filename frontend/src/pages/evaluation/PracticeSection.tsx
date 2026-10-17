// D3：练习建议
import { Card } from '@/components/ui/card'
import { useTranslation } from 'react-i18next'
import type { UnifiedPracticeCard } from '@/types/interviewLearning'

export function PracticeSection({
  cards,
  onPractice,
}: {
  cards: UnifiedPracticeCard[]
  onPractice: (focusTopic: string) => void
}) {
  const { t } = useTranslation('evaluation')
  return (
    <section className="app-eval-zone">
      <Card className="app-panel app-eval-practice-panel">
        <div className="app-eval-practice-panel-head">
          <h3>{t('practice_title')}</h3>
          <p>{t('practice_subtitle')}</p>
        </div>
        <div className="app-eval-practice-body">
          <div className="app-eval-practice-rows">
            {cards.map((card) => (
              <div key={card.id} className="app-eval-practice-row">
                <div className="app-eval-practice-row-copy">
                  <strong>{card.title}</strong>
                  <p>{card.summary}</p>
                </div>
                <button
                  type="button"
                  className="app-btn-confirm app-eval-practice-row-btn"
                  onClick={() => onPractice(card.focus_topic)}
                >
                  {t('practice_retry_btn')}
                </button>
              </div>
            ))}
          </div>
        </div>
      </Card>
    </section>
  )
}
