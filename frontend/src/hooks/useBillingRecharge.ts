/** v2.3 充值后统一刷新用户状态。
 *
 * 根因：BillingPanel.onRecharged 把 `status.quota_remaining` 合并到 user 缓存，
 * 导致 AppSidebar / Quota 仍按原值渲染（出现 "10000"）。
 *
 * 修复：充值成功后调用 getMe 重新拉取权威 user profile，**不**本地合并。
 */
import { useCallback, useState } from 'react'
import { getMe } from '@/services/auth'
import type { UserProfile } from '@/types/auth'

export interface UseBillingRechargeOptions {
  token: string
}

export interface UseBillingRechargeResult {
  /** 触发刷新（充值成功后）。返回最新 user。 */
  refreshUser: () => Promise<UserProfile | null>
  loading: boolean
  error: string | null
}

export function useBillingRecharge({ token }: UseBillingRechargeOptions): UseBillingRechargeResult {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refreshUser = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const fresh = await getMe(token)
      // 调用方应把 fresh 写回 queryClient 缓存的 user
      return fresh
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      return null
    } finally {
      setLoading(false)
    }
  }, [token])

  return { refreshUser, loading, error }
}
