/** 语言切换：醒目 Pill 风格。v2.2: 按钮带 Globe 图标 + 当前语言高亮 + 提示可切到另一语言。 */
import { useTranslation } from 'react-i18next'
import { Globe, Languages } from 'lucide-react'

export function LanguageSwitcher() {
  const { i18n, t } = useTranslation('sidebar')
  const current = (i18n.language || 'en').split('-')[0]
  const isZh = current === 'zh'

  function changeTo(lng: 'en' | 'zh') {
    if (i18n.language === lng) return
    void i18n.changeLanguage(lng)
  }

  return (
    <div className="v2-lang-switcher-prominent" role="group" aria-label={t('language')}>
      <Languages size={16} aria-hidden="true" className="v2-lang-switcher-icon" />
      <button
        type="button"
        className={`v2-lang-option${!isZh ? ' v2-lang-option-active' : ''}`}
        onClick={() => changeTo('en')}
        aria-pressed={!isZh}
        title={isZh ? 'Switch to English' : '当前语言：English'}
      >
        <span className="v2-lang-emoji" aria-hidden="true">🇺🇸</span>
        <span>EN</span>
        {!isZh ? <span className="v2-lang-pill-current" aria-hidden="true">●</span> : null}
      </button>
      <span className="v2-lang-sep" aria-hidden="true">|</span>
      <button
        type="button"
        className={`v2-lang-option${isZh ? ' v2-lang-option-active' : ''}`}
        onClick={() => changeTo('zh')}
        aria-pressed={isZh}
        title={isZh ? '当前语言：中文' : 'Switch to 中文'}
      >
        <span className="v2-lang-emoji" aria-hidden="true">🇨🇳</span>
        <span>中文</span>
        {isZh ? <span className="v2-lang-pill-current" aria-hidden="true">●</span> : null}
      </button>
      <Globe size={14} aria-hidden="true" className="v2-lang-switcher-globe" />
    </div>
  )
}
