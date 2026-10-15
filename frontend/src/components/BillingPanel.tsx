/** v2.2 充值面板：2 个档位卡片 + 模拟支付。 */
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { CheckCircle2, Loader2, Sparkles, Zap } from 'lucide-react'
import {
  getPackages,
  recharge,
  type BillingPackage,
  type BillingUserStatus,
} from '@/services/billing'

interface BillingPanelProps {
  open: boolean
  onClose: () => void
  token: string
  onRecharged: (status: BillingUserStatus) => void
}

type PayState = 'idle' | 'loading' | 'paying' | 'success' | 'error'

export function BillingPanel({ open, onClose, token, onRecharged }: BillingPanelProps) {
  const { t, i18n } = useTranslation('billing')
  const { t: tc } = useTranslation('common')
  const [packages, setPackages] = useState<BillingPackage[]>([])
  const [status, setStatus] = useState<BillingUserStatus | null>(null)
  const [payState, setPayState] = useState<PayState>('idle')
  const [payingPkg, setPayingPkg] = useState<string>('')
  const [error, setError] = useState<string>('')

  const isEn = (i18n.language || 'en').split('-')[0] === 'en'

  useEffect(() => {
    if (!open) return
    setPayState('loading')
    setError('')
    getPackages(token)
      .then((r) => {
        setPackages(r.packages)
        setStatus(r.user)
        setPayState('idle')
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : tc('request_failed'))
        setPayState('error')
      })
  }, [open, token, tc])

  async function handlePay(pkg: BillingPackage) {
    if (payState === 'paying') return
    setPayingPkg(pkg.id)
    setPayState('paying')
    setError('')
    try {
      const r = await recharge(token, pkg.id)
      setStatus(r.user)
      onRecharged(r.user)
      setPayState('success')
      window.setTimeout(() => setPayState('idle'), 2000)
    } catch (err) {
      setError(err instanceof Error ? err.message : tc('request_failed'))
      setPayState('error')
    } finally {
      setPayingPkg('')
    }
  }

  if (!open) return null

  return (
    <div className="v2-billing-overlay" role="dialog" aria-modal="true" aria-label={t('title')}>
      <div className="v2-billing-modal">
        <div className="v2-billing-header">
          <h2>{t('title')}</h2>
          <button type="button" className="v2-billing-close" onClick={onClose} aria-label={tc('close')}>
            ×
          </button>
        </div>
        {status ? (
          <div className="v2-billing-status">
            <span className="v2-billing-tier-tag" data-tier={status.tier}>
              {t(`tier_${status.tier}`)}
            </span>
            <strong>
              {t('quota_left', { count: status.quota_remaining })}
            </strong>
            {status.subscription_expires_at ? (
              <small>{t('sub_expires_at', { date: status.subscription_expires_at.slice(0, 10) })}</small>
            ) : null}
          </div>
        ) : null}
        {payState === 'loading' ? (
          <div className="v2-billing-loading">
            <Loader2 className="animate-spin" />
          </div>
        ) : null}
        <div className="v2-billing-grid">
          {packages.map((pkg) => {
            const isPaying = payState === 'paying' && payingPkg === pkg.id
            const isSuccess = payState === 'success' && payingPkg === '' // already paid
            return (
              <Card key={pkg.id} className="v2-billing-card">
                <div className="v2-billing-card-head">
                  {pkg.id === 'subscription' ? <Sparkles size={20} /> : <Zap size={20} />}
                  <h3>{isEn ? pkg.title_en : pkg.title_zh}</h3>
                </div>
                <p className="v2-billing-tagline">{isEn ? pkg.tagline_en : pkg.tagline_zh}</p>
                <div className="v2-billing-price">
                  <strong>¥{(pkg.price_cents / 100).toFixed(0)}</strong>
                  <span>
                    {pkg.id === 'subscription'
                      ? t('per_month')
                      : t('per_package', { count: pkg.interviews ?? 0 })}
                  </span>
                </div>
                <Button
                  type="button"
                  className="v2-billing-cta"
                  disabled={payState === 'loading' || isPaying}
                  onClick={() => void handlePay(pkg)}
                >
                  {isPaying ? (
                    <>
                      <Loader2 className="animate-spin" size={14} /> {t('paying')}
                    </>
                  ) : isSuccess ? (
                    <>
                      <CheckCircle2 size={14} /> {t('paid')}
                    </>
                  ) : (
                    <>{t('pay_now')}</>
                  )}
                </Button>
                <small className="v2-billing-mock-note">{t('mock_note')}</small>
              </Card>
            )
          })}
        </div>
        {error ? <p className="v2-error">{error}</p> : null}
      </div>
    </div>
  )
}
