export interface UserProfile {
  id: number
  username: string
  quota_remaining: number
  tier?: string
  subscription_expires_at?: string | null
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: UserProfile
}
