export interface UserProfile {
  id: number
  username: string
  // v2.3: 订阅有效时为 null（=无限）
  quota_remaining: number | null
  tier?: string
  // v2.3: 单一权威会员状态
  membership_status?: 'free' | 'active_subscription' | 'expired_subscription' | 'paid'
  subscription_expires_at?: string | null
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: UserProfile
}
