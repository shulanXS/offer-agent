/** v2.2/v2.3/v2.5 充值 API 客户端。 */
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
  // v2.3: 订阅有效时为 null（=无限）
  quota_remaining: number | null
  membership_status: 'free' | 'active_subscription' | 'expired_subscription' | 'paid'
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

// v2.5：真实支付订单
export type OrderStatus = 'pending' | 'paid' | 'failed' | 'cancelled'

export interface PaymentOrder {
  id: string
  package: 'single' | 'subscription'
  amount_cents: number
  provider: 'mock' | 'stripe' | 'alipay' | string
  provider_order_id: string | null
  checkout_url: string | null
  status: OrderStatus
  subject: string | null
  created_at: string
  paid_at: string | null
  metadata: Record<string, unknown>
}

export interface CreateOrderResponse {
  order: PaymentOrder
  user: BillingUserStatus
}

export interface OrderStatusResponse {
  order: PaymentOrder
  user: BillingUserStatus
}

export function getPackages(token: string) {
  return requestJson<BillingPackagesResponse>('/api/billing/packages', {}, token)
}

/** 旧版兼容：mock 即时入账。新代码请走 createOrder + mockConfirm。 */
export function recharge(
  token: string,
  packageId: 'single' | 'subscription',
  idempotencyKey?: string,
) {
  return requestJson<RechargeResponse>(
    '/api/billing/recharge',
    {
      method: 'POST',
      body: JSON.stringify({
        package: packageId,
        idempotency_key: idempotencyKey,
      }),
    },
    token,
  )
}

export function getHistory(token: string) {
  return requestJson<PaymentRecord[]>('/api/billing/history', {}, token)
}

/** v2.5：创建真实支付订单，返回 checkout_url。 */
export function createOrder(
  token: string,
  packageId: 'single' | 'subscription',
  options: { idempotencyKey?: string; provider?: string } = {},
) {
  return requestJson<CreateOrderResponse>(
    '/api/billing/orders',
    {
      method: 'POST',
      body: JSON.stringify({
        package: packageId,
        idempotency_key: options.idempotencyKey,
        provider: options.provider,
      }),
    },
    token,
  )
}

/** v2.5：轮询订单状态。 */
export function getOrder(token: string, orderId: string) {
  return requestJson<OrderStatusResponse>(`/api/billing/orders/${orderId}`, {}, token)
}
