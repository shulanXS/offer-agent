export interface UserProfile {
  id: number
  username: string
  quota_remaining: number
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: UserProfile
}
