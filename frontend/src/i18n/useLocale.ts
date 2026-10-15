/** 读当前 i18n 语言（供 Intl.* API 使用）。 */
import { useTranslation } from 'react-i18next'
import type { SupportedLocale } from './index'
import { DEFAULT_LOCALE } from './index'

export function useLocale(): SupportedLocale {
  const { i18n } = useTranslation()
  const raw = (i18n.language || DEFAULT_LOCALE).split('-')[0]
  return (raw === 'zh' ? 'zh' : 'en') as SupportedLocale
}

export function bcp47ForIntl(locale: SupportedLocale): string {
  return locale === 'zh' ? 'zh-CN' : 'en-US'
}
