/**
 * v3.9 实时更新模块
 * 显示面向访客的产品价值更新（不再是技术 changelog）。
 * 每条：做了什么 → 用户能感受到什么。
 */
import { useTranslation } from 'react-i18next'

interface UpdateItem {
  date: string
  /** i18n 中"做了什么"短句的 key */
  headlineKey: 'updates_qbank_headline' | 'updates_logic_headline' | 'updates_resume_headline'
  /** i18n 中"用户能感受到什么"描述的 key */
  descKey: 'updates_qbank_note' | 'updates_logic_note' | 'updates_resume_note'
  /** 显示用的 module 标签 */
  labelKey: 'updates_qbank_label' | 'updates_logic_label' | 'updates_resume_label'
  version: string
}

const UPDATES: UpdateItem[] = [
  {
    date: '2026-10-13',
    headlineKey: 'updates_qbank_headline',
    descKey: 'updates_qbank_note',
    labelKey: 'updates_qbank_label',
    version: 'v2.9.0',
  },
  {
    date: '2026-10-09',
    headlineKey: 'updates_logic_headline',
    descKey: 'updates_logic_note',
    labelKey: 'updates_logic_label',
    version: 'v2.7.0',
  },
  {
    date: '2026-10-02',
    headlineKey: 'updates_resume_headline',
    descKey: 'updates_resume_note',
    labelKey: 'updates_resume_label',
    version: 'v3.1.0',
  },
]

function formatDate(iso: string): string {
  const [, m, d] = iso.split('-')
  return `${Number(m)}.${Number(d)}`
}

export function LiveUpdates() {
  const { t } = useTranslation('common')
  return (
    <section className="app-updates">
      <div className="app-updates-inner">
        <div className="app-updates-head">
          <p className="app-updates-label">{t('updates_label', '它在持续变好')}</p>
          <h2 className="app-updates-title">{t('updates_title', '它最近在变好')}</h2>
          <p className="app-updates-subtitle">{t('updates_subtitle', '')}</p>
        </div>
        <ol className="app-updates-list">
          {UPDATES.map((item) => (
            <li key={`${item.date}-${item.headlineKey}`} className="app-updates-item">
              <time className="app-updates-date" dateTime={item.date}>
                <span className="app-updates-date-num">{formatDate(item.date)}</span>
                <span className="app-updates-date-year">2026</span>
              </time>
              <div className="app-updates-body">
                <div className="app-updates-meta">
                  <span className="app-updates-module">{t(item.labelKey)}</span>
                  <span className="app-updates-version">{item.version}</span>
                </div>
                <h3 className="app-updates-headline">{t(item.headlineKey)}</h3>
                <p className="app-updates-note">{t(item.descKey)}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}
