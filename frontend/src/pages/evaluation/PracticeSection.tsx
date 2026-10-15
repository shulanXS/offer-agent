// D3：练习建议
import { Card } from '@/components/ui/card'
import type { UnifiedPracticeCard } from '@/types/interviewLearning'

export function PracticeSection({
  cards,
  onPractice,
}: {
  cards: UnifiedPracticeCard[]
  onPractice: (focusTopic: string) => void
}) {
  return (
    <section className="v2-eval-zone">
      <Card className="v2-panel v2-eval-practice-panel">
        <div className="v2-eval-practice-panel-head">
          <h3>练习建议</h3>
          <p>基于本场薄弱项，给出可立即开始的重点练习方向。</p>
        </div>
        <div className="v2-eval-practice-body">
          <div className="v2-eval-practice-rows">
            {cards.map((card) => (
              <div key={card.id} className="v2-eval-practice-row">
                <div className="v2-eval-practice-row-copy">
                  <strong>{card.title}</strong>
                  <p>{card.summary}</p>
                </div>
                <button
                  type="button"
                  className="v2-btn-confirm v2-eval-practice-row-btn"
                  onClick={() => onPractice(card.focus_topic)}
                >
                  再练一次
                </button>
              </div>
            ))}
          </div>
        </div>
      </Card>
    </section>
  )
}
