/**
 * v1.1 i18n 初始化（react-i18next + browser-languagedetector）
 *
 * - 默认语言：英文（en）
 * - 启动顺序：先读 localStorage[offer-agent-locale] -> navigator -> fallback en
 * - 切语言：i18n.changeLanguage()；写回 localStorage；同步 <html lang>
 */
import i18n from 'i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import { initReactI18next } from 'react-i18next'

import commonEn from '../locales/en/common.json'
import sidebarEn from '../locales/en/sidebar.json'
import authEn from '../locales/en/auth.json'
import resumesEn from '../locales/en/resumes.json'
import interviewEn from '../locales/en/interview.json'
import evaluationEn from '../locales/en/evaluation.json'
import errorsEn from '../locales/en/errors.json'
import plansEn from '../locales/en/plans.json'
import recordsEn from '../locales/en/records.json'
import billingEn from '../locales/en/billing.json'

import commonZh from '../locales/zh/common.json'
import sidebarZh from '../locales/zh/sidebar.json'
import authZh from '../locales/zh/auth.json'
import resumesZh from '../locales/zh/resumes.json'
import interviewZh from '../locales/zh/interview.json'
import evaluationZh from '../locales/zh/evaluation.json'
import errorsZh from '../locales/zh/errors.json'
import plansZh from '../locales/zh/plans.json'
import recordsZh from '../locales/zh/records.json'
import billingZh from '../locales/zh/billing.json'

export const SUPPORTED_LOCALES = ['en', 'zh'] as const
export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number]
export const DEFAULT_LOCALE: SupportedLocale = 'en'

const STORAGE_KEY = 'offer-agent-locale'

const resources = {
  en: {
    common: commonEn,
    sidebar: sidebarEn,
    auth: authEn,
    resumes: resumesEn,
    interview: interviewEn,
    evaluation: evaluationEn,
    errors: errorsEn,
    plans: plansEn,
    records: recordsEn,
    billing: billingEn,
  },
  zh: {
    common: commonZh,
    sidebar: sidebarZh,
    auth: authZh,
    resumes: resumesZh,
    interview: interviewZh,
    evaluation: evaluationZh,
    errors: errorsZh,
    plans: plansZh,
    records: recordsZh,
    billing: billingZh,
  },
} as const

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: DEFAULT_LOCALE,
    supportedLngs: SUPPORTED_LOCALES as unknown as string[],
    nonExplicitSupportedLngs: true,
    ns: [
      'common',
      'sidebar',
      'auth',
      'resumes',
      'interview',
      'evaluation',
      'errors',
      'plans',
      'records',
      'billing',
    ],
    defaultNS: 'common',
    detection: {
      order: ['localStorage', 'navigator'],
      lookupLocalStorage: STORAGE_KEY,
      caches: ['localStorage'],
    },
    interpolation: {
      escapeValue: false, // React 已经转义
    },
    returnEmptyString: false,
  })

// 初始化 <html lang> 与 localStorage 一致
const initialLng = (i18n.language || DEFAULT_LOCALE).split('-')[0] as SupportedLocale
if (SUPPORTED_LOCALES.includes(initialLng)) {
  document.documentElement.lang = initialLng
} else {
  document.documentElement.lang = DEFAULT_LOCALE
}

i18n.on('languageChanged', (lng) => {
  const next = (lng.split('-')[0] as SupportedLocale) || DEFAULT_LOCALE
  document.documentElement.lang = next
  try {
    localStorage.setItem(STORAGE_KEY, next)
  } catch {
    /* 忽略 localStorage 不可用 */
  }
})

export { STORAGE_KEY, i18n }
export default i18n
