/**
 * v3.6 已登录态的「更新日志」面板
 *
 * 设计目标：
 * - 在 ResumesPage 旁边（侧边或顶部）展示，带原生 scrollbar
 * - 列表包含日期、模块、版本号、说明（i18n）
 * - 视觉上克制，像真实产品的 changelog
 */
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ChevronDown, Sparkles } from 'lucide-react'

interface ReleaseNote {
  date: string
  version: string
  moduleKey: 'updates_persona_note' | 'updates_followup_note' | 'updates_resume_note' | 'updates_payment_note'
  labelKey: 'updates_qbank_label' | 'updates_logic_label' | 'updates_scoring_label' | 'updates_payment_label'
  /** 高亮：本次上线关键变更标题（i18n key，可选） */
  headlineKey?: string
  /** 详细条目（i18n keys） */
  bullets?: string[]
}

const RELEASES: ReleaseNote[] = [
  {
    date: '2026-10-15',
    version: 'v2.5.0',
    moduleKey: 'updates_payment_note',
    labelKey: 'updates_payment_label',
    headlineKey: 'release_v250_headline',
    bullets: [
      'release_v250_bullet_1',
      'release_v250_bullet_2',
      'release_v250_bullet_3',
    ],
  },
  {
    date: '2026-10-13',
    version: 'v2.9.0',
    moduleKey: 'updates_persona_note',
    labelKey: 'updates_qbank_label',
    headlineKey: 'release_v290_headline',
    bullets: ['release_v290_bullet_1', 'release_v290_bullet_2'],
  },
  {
    date: '2026-10-09',
    version: 'v2.7.0',
    moduleKey: 'updates_followup_note',
    labelKey: 'updates_logic_label',
    headlineKey: 'release_v270_headline',
    bullets: ['release_v270_bullet_1', 'release_v270_bullet_2'],
  },
  {
    date: '2026-10-02',
    version: 'v3.1.0',
    moduleKey: 'updates_resume_note',
    labelKey: 'updates_scoring_label',
    headlineKey: 'release_v310_headline',
    bullets: ['release_v310_bullet_1', 'release_v310_bullet_2'],
  },
  {
    date: '2026-09-25',
    version: 'v3.0.0',
    moduleKey: 'updates_resume_note',
    labelKey: 'updates_scoring_label',
    headlineKey: 'release_v300_headline',
    bullets: ['release_v300_bullet_1'],
  },
  {
    date: '2026-09-18',
    version: 'v2.6.0',
    moduleKey: 'updates_persona_note',
    labelKey: 'updates_qbank_label',
    headlineKey: 'release_v260_headline',
    bullets: ['release_v260_bullet_1', 'release_v260_bullet_2'],
  },
  {
    date: '2026-09-10',
    version: 'v2.5.0',
    moduleKey: 'updates_followup_note',
    labelKey: 'updates_logic_label',
    headlineKey: 'release_v250b_headline',
    bullets: ['release_v250b_bullet_1'],
  },
]

function formatDate(iso: string): { num: string; year: string } {
  const [, m, d] = iso.split('-')
  return { num: `${Number(m)}.${Number(d)}`, year: iso.split('-')[0] }
}

export function ReleaseLog() {
  const { t } = useTranslation('common')
  const [expanded, setExpanded] = useState<string | null>(RELEASES[0]?.date ?? null)

  const items = useMemo(() => RELEASES, [])

  return (
    <aside className="release-log" aria-label={t('release_log_aria')}>
      <header className="release-log-head">
        <Sparkles size={14} aria-hidden />
        <span className="release-log-label">{t('release_log_label')}</span>
        <span className="release-log-title">{t('release_log_title')}</span>
        <span className="release-log-subtitle">{t('release_log_subtitle')}</span>
      </header>
      <ol className="release-log-list">
        {items.map((item) => {
          const isOpen = expanded === item.date
          const { num, year } = formatDate(item.date)
          return (
            <li key={item.date} className="release-log-item" data-open={isOpen}>
              <button
                type="button"
                className="release-log-row"
                aria-expanded={isOpen}
                onClick={() => setExpanded(isOpen ? null : item.date)}
              >
                <time className="release-log-date" dateTime={item.date}>
                  <span className="release-log-date-num">{num}</span>
                  <span className="release-log-date-year">{year}</span>
                </time>
                <div className="release-log-row-body">
                  <div className="release-log-meta">
                    <span className="release-log-module">{t(item.labelKey)}</span>
                    <span className="release-log-version">{item.version}</span>
                  </div>
                  <p className="release-log-headline">
                    {item.headlineKey ? t(item.headlineKey) : t(item.moduleKey)}
                  </p>
                </div>
                <ChevronDown
                  size={14}
                  className={`release-log-chevron${isOpen ? ' rotate' : ''}`}
                  aria-hidden
                />
              </button>
              {isOpen && item.bullets && item.bullets.length > 0 ? (
                <ul className="release-log-bullets">
                  {item.bullets.map((b) => (
                    <li key={b}>{t(b)}</li>
                  ))}
                </ul>
              ) : null}
            </li>
          )
        })}
      </ol>
    </aside>
  )
}
