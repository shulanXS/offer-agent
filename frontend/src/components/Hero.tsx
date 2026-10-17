/**
 * v3.4 首页 Hero
 * 左右两栏：
 *   左 = 装饰条 + eyebrow + 大标题 + 副标题 + CTA
 *   右 = 2×2 训练样本差异卡（含"像真人"条）
 */
import { useTranslation } from 'react-i18next'
import { ArrowRight } from 'lucide-react'

export interface HeroProps {
  onStartClick?: () => void
  onRegisterClick?: () => void
}

interface ContrastItem {
  key: string
  num: string
  tag: string
  title: string
  desc: string
  sampleLabel: string
  sampleReply: string
}

export function Hero({ onStartClick, onRegisterClick }: HeroProps) {
  const { t } = useTranslation('common')
  const isAuthenticated = Boolean(onStartClick)

  const contrasts: ContrastItem[] = [
    {
      key: 'pushback',
      num: '01',
      tag: t('selling_point_1_kicker'),
      title: t('selling_point_1_title'),
      desc: t('selling_point_1_desc'),
      sampleLabel: t('selling_point_1_sample_quote'),
      sampleReply: t('selling_point_1_sample_reply'),
    },
    {
      key: 'pool',
      num: '02',
      tag: t('selling_point_2_kicker'),
      title: t('selling_point_2_title'),
      desc: t('selling_point_2_desc'),
      sampleLabel: t('selling_point_2_sample_quote'),
      sampleReply: t('selling_point_2_sample_reply'),
    },
    {
      key: 'evidence',
      num: '03',
      tag: t('selling_point_3_kicker'),
      title: t('selling_point_3_title'),
      desc: t('selling_point_3_desc'),
      sampleLabel: t('selling_point_3_sample_quote'),
      sampleReply: t('selling_point_3_sample_reply'),
    },
    {
      key: 'voice',
      num: '04',
      tag: t('selling_point_4_kicker'),
      title: t('selling_point_4_title'),
      desc: t('selling_point_4_desc'),
      sampleLabel: t('selling_point_4_sample_quote'),
      sampleReply: t('selling_point_4_sample_reply'),
    },
  ]

  return (
    <section className="app-hero">
      <div className="app-hero-inner">
        {/* 左栏：标题 + CTA */}
        <div className="app-hero-main">
          <p className="app-hero-eyebrow">
            <span className="app-hero-eyebrow-dot" aria-hidden />
            {t('hero_eyebrow')}
          </p>
          <h1 className="app-hero-title">{t('hero_title')}</h1>
          <p className="app-hero-lead">{t('hero_lead')}</p>

          <div className="app-hero-cta-row">
            <button
              type="button"
              className="app-hero-cta"
              onClick={isAuthenticated ? onStartClick : onRegisterClick}
            >
              <span>{t('hero_cta_register')}</span>
              <ArrowRight size={17} aria-hidden />
            </button>
          </div>
          <p className="app-hero-cta-note">{t('hero_cta_note')}</p>
        </div>

        {/* 右栏：2×2 训练样本差异卡 */}
        <aside className="app-hero-evidence" aria-label={t('hero_evidence_heading')}>
          {contrasts.map((item) => (
            <article key={item.key} className="app-hero-evidence-card">
              <header className="app-hero-evidence-meta">
                <span className="app-hero-evidence-num">{item.num}</span>
                <span className="app-hero-evidence-tag">{item.tag}</span>
              </header>
              <h3 className="app-hero-evidence-title">{item.title}</h3>
              <p className="app-hero-evidence-desc">{item.desc}</p>
              <div className="app-hero-evidence-sample">
                <div className="app-hero-evidence-sample-label">{item.sampleLabel}</div>
                <div className="app-hero-evidence-sample-reply">
                  <span className="app-hero-evidence-sample-arrow" aria-hidden>↳</span>
                  {item.sampleReply}
                </div>
              </div>
            </article>
          ))}
        </aside>
      </div>
    </section>
  )
}
