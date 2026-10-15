/** 语言切换：EN | 中文。 */
import { useTranslation } from 'react-i18next'
import { Languages } from 'lucide-react'

export function LanguageSwitcher() {
  const { i18n, t } = useTranslation('sidebar')
  const current = (i18n.language || 'en').split('-')[0]
  const isZh = current === 'zh'

  function changeTo(lng: 'en' | 'zh') {
    if (i18n.language === lng) return
    void i18n.changeLanguage(lng)
  }

  return (
    <div className="v2-lang-switcher" role="group" aria-label={t('language')}>
      <Languages size={14} aria-hidden="true" />
      <button
        type="button"
        className={`v2-lang-option${!isZh ? ' v2-lang-option-active' : ''}`}
        onClick={() => changeTo('en')}
        aria-pressed={!isZh}
      >
        EN
      </button>
      <span className="v2-lang-sep" aria-hidden="true">
        |
      </span>
      <button
        type="button"
        className={`v2-lang-option${isZh ? ' v2-lang-option-active' : ''}`}
        onClick={() => changeTo('zh')}
        aria-pressed={isZh}
      >
        中文
      </button>
    </div>
  )
}
