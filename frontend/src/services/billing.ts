/** v2.2 充值 API 客户端。 */
import { requestJson } from './client'

export interface BillingPackage {
  id: 'single' | 'subscription'
  title_zh: string
  title_en: string
  price_cents: number
  interviews: number | null
  duration_days: number | null
  tagline_zh: string
  tagline_en: string
}

export interface BillingUserStatus {
  tier: string
  quota_remaining: number
  subscription_expires_at: string | null
}

export interface BillingPackagesResponse {
  packages: BillingPackage[]
  user: BillingUserStatus
}

export interface PaymentRecord {
  id: string
  user_id: number
  package: string
  amount_cents: number
  interviews_granted: number
  status: string
  created_at: string
  completed_at: string | null
}

export interface RechargeResponse {
  payment: PaymentRecord
  user: BillingUserStatus
}

export function getPackages(token: string) {
  return requestJson<BillingPackagesResponse>('/api/billing/packages', {}, token)
}

export function recharge(token: string, packageId: 'single' | 'subscription') {
  return requestJson<RechargeResponse>(
    '/api/billing/recharge',
    {
      method: 'POST',
      body: JSON.stringify({ package: packageId }),
    },
    token,
  )
}

export function getHistory(token: string) {
  return requestJson<PaymentRecord[]>('/api/billing/history', {}, token)
}
