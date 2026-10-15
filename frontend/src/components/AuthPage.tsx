import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useTranslation } from 'react-i18next'
import type { ReactNode } from 'react'

export type AuthMode = 'login' | 'register'

interface AuthPageProps {
  authMode: AuthMode
  error: string
  isSubmitting: boolean
  notice: string
  password: string
  username: string
  leadingSlot?: ReactNode
  onAuthModeChange: (mode: AuthMode) => void
  onPasswordChange: (value: string) => void
  onSubmit: () => Promise<void>
  onUsernameChange: (value: string) => void
}

export function AuthPage({
  authMode,
  error,
  isSubmitting,
  notice,
  password,
  username,
  leadingSlot,
  onAuthModeChange,
  onPasswordChange,
  onSubmit,
  onUsernameChange,
}: AuthPageProps) {
  const { t } = useTranslation('auth')
  const { t: tc } = useTranslation('common')
  return (
    <main className="v2-shell v2-auth-shell">
      {leadingSlot ? <div className="v2-auth-leading">{leadingSlot}</div> : null}
      <Card className="v2-auth-card">
        <span className="v2-kicker">{t('kicker')}</span>
        <h1>{t('headline')}</h1>
        <p>{t('subhead')}</p>
        <div className="v2-auth-tabs">
          <Button
            variant={authMode === 'login' ? 'default' : 'outline'}
            onClick={() => onAuthModeChange('login')}
          >
            {t('tab_login')}
          </Button>
          <Button
            variant={authMode === 'register' ? 'default' : 'outline'}
            onClick={() => onAuthModeChange('register')}
          >
            {t('tab_register')}
          </Button>
        </div>
        <form
          className="v2-auth-form"
          onSubmit={(event) => {
            event.preventDefault()
            void onSubmit()
          }}
        >
          <Label>
            {t('label_username')}
            <Input value={username} onChange={(event) => onUsernameChange(event.target.value)} required />
          </Label>
          <Label>
            {t('label_password')}
            <Input
              type="password"
              value={password}
              onChange={(event) => onPasswordChange(event.target.value)}
              required
            />
          </Label>
          {notice ? <p className="v2-notice">{notice}</p> : null}
          {error ? <p className="v2-error">{error}</p> : null}
          <Button type="submit" disabled={isSubmitting || !username.trim() || !password}>
            {isSubmitting ? tc('submitting') : authMode === 'login' ? t('submit_login') : t('submit_register')}
          </Button>
        </form>
      </Card>
    </main>
  )
}

export function AuthLoading() {
  const { t } = useTranslation('common')
  return (
    <main className="v2-shell v2-auth-shell">
      <Card className="v2-auth-card">
        <span className="v2-kicker">AI</span>
        <p>{t('loading')}</p>
      </Card>
    </main>
  )
}
