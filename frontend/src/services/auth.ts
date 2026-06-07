import type { AuthResponse, UserProfile } from '@/types'
import { requestJson } from './client'

export function register(username: string, password: string) {
  return requestJson<AuthResponse>('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

export function login(username: string, password: string) {
  return requestJson<AuthResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

export function getMe(token: string) {
  return requestJson<UserProfile>('/api/auth/me', {}, token)
}
