// D3：评估降级提示（B1 配套）
import { useTranslation } from 'react-i18next'
import type { ScorePresentation } from '../evaluation/utils'

export function DegradedBanner({ presentation }: { presentation: ScorePresentation }) {
  const { t } = useTranslation('evaluation')
  if (!presentation.degraded) return null
  return (
    <section className="app-eval-zone">
      <div className="app-eval-degraded-banner" role="alert">
        <strong>{t('degraded_banner_title')}</strong>
        <p>{presentation.degradedMessage || t('degraded_banner_body')}</p>
        {presentation.degradedReason ? (
          <p className="app-eval-degraded-reason">
            {t('degraded_banner_reason_label', { reason: presentation.degradedReason })}
          </p>
        ) : null}
      </div>
    </section>
  )
}
