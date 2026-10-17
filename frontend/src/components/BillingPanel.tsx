/** v2.5 充值面板：polished 付费页（真实 Stripe Checkout + 会员状态、套餐对比、信任标识、FAQ）。

- 点击「立即支付」：调用 `createOrder` 拿到 `checkout_url`（Stripe Checkout 收银台）。
- `window.location` 跳转到 Stripe 完成支付。
- 支付完成后 Stripe 通过 success_url 回跳到 `/billing/return?order_id=...&status=success|cancel`，
  由 `BillingReturnPage` 轮询订单状态 + 刷新 user。
- 通道未配置（`STRIPE_SECRET_KEY` 缺失）时 createOrder 返回 503，前端展示明确错误。
*/
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { CheckCircle2, Loader2, ShieldCheck, Sparkles, Zap, ChevronDown, Clock, Lock, BadgeCheck, AlertCircle } from 'lucide-react'
import {
  createOrder,
  getPackages,
  type BillingPackage,
  type BillingUserStatus,
} from '@/services/billing'

interface BillingPanelProps {
  open: boolean
  onClose: () => void
  token: string
  onRecharged: () => void | Promise<void>
}

type PayState = 'idle' | 'loading' | 'creating' | 'redirecting' | 'success' | 'error'

const TRUST_BADGES = [
  { icon: ShieldCheck, key: 'trust_security' },
  { icon: Lock, key: 'trust_privacy' },
  { icon: BadgeCheck, key: 'trust_invoice' },
  { icon: Clock, key: 'trust_instant' },
] as const

export function BillingPanel({ open, onClose, token, onRecharged }: BillingPanelProps) {
  const { t } = useTranslation('billing')
  const { t: tc } = useTranslation('common')
  const { i18n } = useTranslation('common')
  const isEn = (i18n.language || 'en').split('-')[0] === 'en'
  const [packages, setPackages] = useState<BillingPackage[]>([])
  const [status, setStatus] = useState<BillingUserStatus | null>(null)
  const [payState, setPayState] = useState<PayState>('idle')
  const [payingPkg, setPayingPkg] = useState<string>('')
  const [error, setError] = useState<string>('')
  const [faqOpen, setFaqOpen] = useState<string | null>(null)

  // v3.7：Esc 关闭充值面板（仅在 idle / success 状态允许，避免支付中误触）
  useEffect(() => {
    if (!open) return
    function onKey(event: KeyboardEvent) {
      if (event.key !== 'Escape') return
      if (payState === 'creating' || payState === 'redirecting') return
      onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, payState, onClose])

  useEffect(() => {
    if (!open) return
    // eslint-disable-next-line react-hooks/set-state-in-effect
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

  // Stripe 回调后回跳到本页：localStorage 标记，刷新 user 状态
  useEffect(() => {
    if (!open) return
    try {
      const raw = localStorage.getItem('offer-agent:recharged')
      if (raw) {
        const data = JSON.parse(raw) as { at: number; orderId: string; user: BillingUserStatus }
        if (Date.now() - data.at < 5 * 60_000 && data.user) {
          // eslint-disable-next-line react-hooks/set-state-in-effect
          setStatus(data.user)
          // eslint-disable-next-line react-hooks/set-state-in-effect
          setPayState('success')
          localStorage.removeItem('offer-agent:recharged')
          setTimeout(() => setPayState('idle'), 2200)
        }
      }
    } catch {
      /* 忽略 */
    }
  }, [open])

  async function handlePay(pkg: BillingPackage) {
    if (payState === 'creating' || payState === 'redirecting') return
    setPayingPkg(pkg.id)
    setPayState('creating')
    setError('')
    // eslint-disable-next-line react-hooks/purity
    const idempotencyKey = generateIdempotencyKey(pkg.id)
    try {
      const r = await createOrder(token, pkg.id, { idempotencyKey })
      setStatus(r.user)
      const checkoutUrl = r.order.checkout_url
      if (!checkoutUrl) {
        setError(t('no_checkout_url'))
        setPayState('error')
        return
      }
      // 记录订单 id，return 页用来回填 user
      try {
        localStorage.setItem(
          'offer-agent:last-order',
          // eslint-disable-next-line react-hooks/purity -- 事件处理器中记录订单时间戳
          JSON.stringify({ at: Date.now(), orderId: r.order.id }),
        )
      } catch {
        /* 忽略 */
      }
      setPayState('redirecting')
      onClose()
      setTimeout(() => {
        window.location.href = checkoutUrl
      }, 50)
      void onRecharged()
    } catch (err) {
      setError(err instanceof Error ? err.message : tc('request_failed'))
      setPayState('error')
    } finally {
      setPayingPkg('')
    }
  }

  const orderedPackages = useMemo(() => {
    return [...packages].sort((a, b) => {
      if (a.id === 'subscription') return -1
      if (b.id === 'subscription') return 1
      return 0
    })
  }, [packages])

  if (!open) return null

  const isActiveSubscription = status?.membership_status === 'active_subscription'

  return (
    <div className="app-billing-overlay" role="dialog" aria-modal="true" aria-label={t('title')}>
      <div className="app-billing-modal">
        <header className="app-billing-header">
          <div>
            <p className="app-billing-eyebrow">{t('eyebrow')}</p>
            <h2>{t('title')}</h2>
            <p className="app-billing-subtitle">{t('subtitle')}</p>
          </div>
          <button type="button" className="app-billing-close" onClick={onClose} aria-label={tc('close')}>
            ×
          </button>
        </header>

        {status ? (
          <section className="app-billing-status" data-status={status.membership_status}>
            <div className="app-billing-status-tier">
              <span className="app-billing-tier-tag" data-tier={status.tier}>
                {t(`tier_${status.tier}`)}
              </span>
              <strong className="app-billing-status-quota">
                {status.quota_remaining === null
                  ? t('unlimited')
                  : t('quota_left', { count: status.quota_remaining })}
              </strong>
            </div>
            {status.subscription_expires_at ? (
              <small className="app-billing-status-expires">
                {t('sub_expires_at', { date: status.subscription_expires_at.slice(0, 10) })}
              </small>
            ) : null}
            {isActiveSubscription ? (
              <p className="app-billing-status-note">{t('sub_active_note')}</p>
            ) : null}
          </section>
        ) : null}

        {/* v3.9：套餐之前的「先看问答」快捷入口 — 减少用户对未知的焦虑 */}
        <div className="app-billing-faq-cta">
          <button
            type="button"
            className="app-billing-faq-cta-btn"
            onClick={() => {
              const el = document.querySelector('.app-billing-faq')
              el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
            }}
          >
            {t('faq_jump_cta')}
          </button>
        </div>

        {payState === 'loading' ? (
          <div className="app-billing-loading">
            <Loader2 className="animate-spin" />
            <span>{tc('loading')}</span>
          </div>
        ) : (
          <section className="app-billing-grid">
            {orderedPackages.map((pkg) => {
              const isRecommended = pkg.id === 'subscription'
              const isPaying =
                (payState === 'creating' || payState === 'redirecting') && payingPkg === pkg.id
              const isJustPaid = payState === 'success' && payingPkg === ''
              const price = (pkg.price_cents / 100).toFixed(0)
              const unit = pkg.id === 'subscription' ? t('per_month') : t('per_package', { count: pkg.interviews ?? 0 })
              const features = pkg.id === 'subscription'
                ? [
                    t('feature_unlimited'),
                    t('feature_priority_queue'),
                    t('feature_full_reports'),
                    t('feature_priority_support'),
                  ]
                : [
                    t('feature_n_interviews', { count: pkg.interviews ?? 0 }),
                    t('feature_full_reports'),
                    t('feature_valid_90_days', { days: 90 }),
                  ]
              return (
                <Card
                  key={pkg.id}
                  className={`app-billing-card${isRecommended ? ' app-billing-card-recommended' : ''}`}
                  data-pkg={pkg.id}
                >
                  {isRecommended ? (
                    <span className="app-billing-recommend-tag">
                      <Sparkles size={12} /> {t('recommended')}
                    </span>
                  ) : null}
                  <div className="app-billing-card-head">
                    {pkg.id === 'subscription' ? <Sparkles size={20} /> : <Zap size={20} />}
                    <div>
                      <h3>{pkgLocalizedName(pkg, isEn, 'title')}</h3>
                      <p className="app-billing-tagline">{pkgLocalizedName(pkg, isEn, 'tagline')}</p>
                    </div>
                  </div>
                  <div className="app-billing-price">
                    <span className="app-billing-price-currency">¥</span>
                    <strong>{price}</strong>
                    <span className="app-billing-price-unit">{unit}</span>
                  </div>
                  <ul className="app-billing-features">
                    {features.map((feat) => (
                      <li key={feat}>
                        <CheckCircle2 size={14} aria-hidden />
                        <span>{feat}</span>
                      </li>
                    ))}
                  </ul>
                  <Button
                    type="button"
                    className={`app-billing-cta${isRecommended ? ' app-billing-cta-primary' : ''}`}
                    disabled={isPaying || payState === 'success'}
                    onClick={() => void handlePay(pkg)}
                  >
                    {isPaying ? (
                      <>
                        <Loader2 className="animate-spin" size={14} /> {t('creating_order')}
                      </>
                    ) : isJustPaid ? (
                      <>
                        <CheckCircle2 size={14} /> {t('paid')}
                      </>
                    ) : (
                      <>{t('pay_now')}</>
                    )}
                  </Button>
                  <small className="app-billing-provider-note">
                    <Lock size={11} /> {t('stripe_note')}
                  </small>
                </Card>
              )
            })}
          </section>
        )}

        {/* 信任标识 */}
        <section className="app-billing-trust" aria-label={t('trust_aria')}>
          {TRUST_BADGES.map(({ icon: Icon, key }) => (
            <div key={key} className="app-billing-trust-item">
              <Icon size={16} aria-hidden />
              <span>{t(key)}</span>
            </div>
          ))}
        </section>

        {/* 常见问题：v3.9 默认展开前 2 条（最高频），其他折叠 */}
        <section className="app-billing-faq" aria-label={t('faq_aria')}>
          <div className="app-billing-faq-head">
            <h4>{t('faq_title')}</h4>
            <span className="app-billing-faq-hint">{t('faq_hint')}</span>
          </div>
          {([
            { qKey: 'faq_q1', aKey: 'faq_a1', openByDefault: true },
            { qKey: 'faq_q2', aKey: 'faq_a2', openByDefault: true },
            { qKey: 'faq_q4', aKey: 'faq_a4', openByDefault: true },
            { qKey: 'faq_q3', aKey: 'faq_a3', openByDefault: true },
            { qKey: 'faq_q7', aKey: 'faq_a7', openByDefault: false },
            { qKey: 'faq_q6', aKey: 'faq_a6', openByDefault: false },
            { qKey: 'faq_q5', aKey: 'faq_a5', openByDefault: false },
            { qKey: 'faq_q8', aKey: 'faq_a8', openByDefault: false },
          ] as const).map(({ qKey, aKey, openByDefault }) => {
            const isOpen = openByDefault || faqOpen === qKey
            return (
              <details
                key={qKey}
                className="app-billing-faq-item"
                open={isOpen}
                onToggle={(event) => {
                  if (!openByDefault) {
                    setFaqOpen((event.currentTarget as HTMLDetailsElement).open ? qKey : null)
                  }
                }}
              >
                <summary>
                  {t(qKey)}
                  <ChevronDown size={14} className={isOpen ? 'rotate' : ''} aria-hidden />
                </summary>
                <p>{t(aKey)}</p>
              </details>
            )
          })}
        </section>

        {error ? (
          <p className="app-billing-error" role="alert">
            <AlertCircle size={14} aria-hidden />
            <span>{error}</span>
          </p>
        ) : null}

        {/* 兜底：FAQ 没覆盖到的问题 → 直接联系 */}
        <div className="app-billing-contact">
          <span>{t('contact_still_have_question')}</span>
          <a href={`mailto:${t('contact_email')}`}>{t('contact_email_cta')}</a>
        </div>
      </div>
    </div>
  )
}

function pkgLocalizedName(
  pkg: BillingPackage,
  isEn: boolean,
  kind: 'title' | 'tagline',
): string {
  if (kind === 'title') return isEn ? pkg.title_en : pkg.title_zh
  return isEn ? pkg.tagline_en : pkg.tagline_zh
}

/** 生成支付订单的幂等 key：在事件回调中调用，无需纯函数 */
function generateIdempotencyKey(pkgId: string): string {
  // eslint-disable-next-line react-hooks/purity
  return `${pkgId}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}
