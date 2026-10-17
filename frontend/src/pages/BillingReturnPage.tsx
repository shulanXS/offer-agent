/** v2.5 Stripe 回调落地页。

Stripe Checkout 通过 success_url / cancel_url 把用户回跳到：
  `{frontend_base_url}/billing/return?order_id=...&status=success|cancel`

- 成功：轮询订单状态直到 paid（webhook 入账是异步的），把 user 状态写入
  `localStorage['offer-agent:recharged']`，跳转回首页（BillingPanel 会自动读取）。
- 取消：直接回首页。
- 订单不存在：提示并提供返回入口。
*/
import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { CheckCircle2, Loader2, XCircle, ShieldCheck } from 'lucide-react'
import { getOrder, type BillingUserStatus } from '@/services/billing'
import { getMe } from '@/services/auth'
import { ApiError, getStoredToken } from '@/services/client'
import { Button } from '@/components/ui/button'

type Phase = 'polling' | 'success' | 'cancelled' | 'failed'

const POLL_INTERVAL_MS = 2000
const POLL_TIMEOUT_MS = 60_000

export function BillingReturnPage() {
  const { t } = useTranslation('billing')
  const { t: tc } = useTranslation('common')
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const orderId = params.get('order_id') || ''
  const status = (params.get('status') || '') as 'success' | 'cancel' | ''
  const [phase, setPhase] = useState<Phase>(status === 'cancel' ? 'cancelled' : 'polling')
  const [error, setError] = useState('')
  const token = getStoredToken()
  const timeoutRef = useRef<number | null>(null)

  const finish = useCallback(
    (user: BillingUserStatus) => {
      try {
        localStorage.setItem(
          'offer-agent:recharged',
          JSON.stringify({ at: Date.now(), orderId, user }),
        )
      } catch {
        /* 忽略 */
      }
      // 跳回 /resumes，BillingPanel 已经在 App 树里不会自动打开，但回到首页后
      // 用户可手动再开 BillingPanel 看到已生效的最新状态。
      setTimeout(() => navigate('/resumes', { replace: true }), 1200)
    },
    [navigate, orderId],
  )

  useEffect(() => {
    if (!token) {
      setError(tc('unauthorized'))
      setPhase('failed')
      return
    }
    if (!orderId) {
      setError(t('return_missing_order'))
      setPhase('failed')
      return
    }
    if (status === 'cancel') {
      setPhase('cancelled')
      return
    }

    let cancelled = false
    const startedAt = Date.now()

    const pollOnce = async (): Promise<BillingUserStatus | null> => {
      try {
        const r = await getOrder(token, orderId)
        if (cancelled) return null
        if (r.order.status === 'paid') {
          setPhase('success')
          return r.user
        }
        return null
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          setError(t('return_order_not_found'))
          setPhase('failed')
          return null
        }
        throw err
      }
    }

    const tick = async () => {
      if (cancelled) return
      if (Date.now() - startedAt > POLL_TIMEOUT_MS) {
        setError(t('return_timeout'))
        setPhase('failed')
        return
      }
      try {
        const user = await pollOnce()
        if (user) {
          finish(user)
          return
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : tc('request_failed'))
        setPhase('failed')
        return
      }
      timeoutRef.current = window.setTimeout(tick, POLL_INTERVAL_MS)
    }

    // 同时拉一次 user 兜底（webhook 还没到，但 user 已经被其他流程刷新过）
    const bootstrap = async () => {
      try {
        const fresh = await getMe(token)
        if (cancelled) return
        if (fresh.membership_status === 'active_subscription' || fresh.quota_remaining === null) {
          setPhase('success')
          finish(fresh)
          return
        }
      } catch {
        /* 忽略；继续轮询 */
      }
      void tick()
    }

    void bootstrap()

    return () => {
      cancelled = true
      if (timeoutRef.current) {
        window.clearTimeout(timeoutRef.current)
      }
    }
  }, [token, orderId, status, t, tc, finish])

  const handleBack = () => {
    navigate('/resumes', { replace: true })
  }

  return (
    <main className="billing-return">
      <div className="billing-return-card" role="status" aria-live="polite">
        <div className="billing-return-icon">
          {phase === 'polling' ? (
            <Loader2 size={28} className="animate-spin" />
          ) : phase === 'success' ? (
            <CheckCircle2 size={28} />
          ) : phase === 'cancelled' ? (
            <XCircle size={28} />
          ) : (
            <XCircle size={28} />
          )}
        </div>
        <h1 className="billing-return-title">
          {phase === 'polling'
            ? t('return_processing')
            : phase === 'success'
              ? t('return_success')
              : phase === 'cancelled'
                ? t('return_cancelled')
                : t('return_failed')}
        </h1>
        <p className="billing-return-sub">
          {phase === 'polling'
            ? t('return_processing_sub')
            : phase === 'success'
              ? t('return_success_sub')
              : phase === 'cancelled'
                ? t('return_cancelled_sub')
                : error}
        </p>
        {phase !== 'polling' ? (
          <div className="billing-return-actions">
            <Button type="button" onClick={handleBack} className="billing-return-cta">
              {t('return_back')}
            </Button>
          </div>
        ) : (
          <div className="billing-return-meta">
            <ShieldCheck size={14} aria-hidden />
            <span>{t('stripe_note')}</span>
          </div>
        )}
      </div>
    </main>
  )
}
