/** v2.2 卖点差异化：3 张卡片，强调「3000+ 真实面试数据 + 证据链 + 可追溯评分」 */
import { useTranslation } from 'react-i18next'
import { Database, ShieldCheck, Workflow } from 'lucide-react'

interface SellingHighlightsProps {
  compact?: boolean
}

export function SellingHighlights({ compact = false }: SellingHighlightsProps) {
  const { t } = useTranslation('common')
  const items = [
    {
      key: 'data',
      icon: Database,
      title: t('selling_point_1_title'),
      desc: t('selling_point_1_desc'),
    },
    {
      key: 'flow',
      icon: Workflow,
      title: t('selling_point_2_title'),
      desc: t('selling_point_2_desc'),
    },
    {
      key: 'evidence',
      icon: ShieldCheck,
      title: t('selling_point_3_title'),
      desc: t('selling_point_3_desc'),
    },
  ]
  return (
    <section className={`v2-selling-highlights${compact ? ' v2-selling-highlights-compact' : ''}`}>
      {items.map((item) => {
        const Icon = item.icon
        return (
          <article key={item.key} className="v2-selling-card">
            <div className="v2-selling-icon" aria-hidden="true">
              <Icon size={22} />
            </div>
            <div>
              <h3>{item.title}</h3>
              <p>{item.desc}</p>
            </div>
          </article>
        )
      })}
    </section>
  )
}
