/** 语言切换：醒目 Pill 风格。v2.2: 按钮带 Globe 图标 + 当前语言高亮 + 提示可切到另一语言。 */
import { useTranslation } from 'react-i18next'
import { Globe, Languages } from 'lucide-react'

export function LanguageSwitcher() {
  const { i18n, t } = useTranslation('sidebar')
  const { t: ti } = useTranslation('interview')
  const current = (i18n.language || 'en').split('-')[0]
  const isZh = current === 'zh'

  function changeTo(lng: 'en' | 'zh') {
    if (i18n.language === lng) return
    void i18n.changeLanguage(lng)
  }

  return (
    <div className="app-lang-switcher-prominent" role="group" aria-label={t('language')}>
      <Languages size={16} aria-hidden="true" className="app-lang-switcher-icon" />
      <button
        type="button"
        className={`app-lang-option${!isZh ? ' app-lang-option-active' : ''}`}
        onClick={() => changeTo('en')}
        aria-pressed={!isZh}
        title={isZh ? ti('lang_switcher_switch_to_en') : ti('lang_switcher_current_en')}
      >
        <span className="app-lang-emoji" aria-hidden="true">🇺🇸</span>
        <span>EN</span>
        {!isZh ? <span className="app-lang-pill-current" aria-hidden="true">●</span> : null}
      </button>
      <span className="app-lang-sep" aria-hidden="true">|</span>
      <button
        type="button"
        className={`app-lang-option${isZh ? ' app-lang-option-active' : ''}`}
        onClick={() => changeTo('zh')}
        aria-pressed={isZh}
        title={isZh ? ti('lang_switcher_current_zh') : ti('lang_switcher_switch_to_zh')}
      >
        <span className="app-lang-emoji" aria-hidden="true">🇨🇳</span>
        <span>{ti('lang_option_zh')}</span>
        {isZh ? <span className="app-lang-pill-current" aria-hidden="true">●</span> : null}
      </button>
      <Globe size={14} aria-hidden="true" className="app-lang-switcher-globe" />
    </div>
  )
}
