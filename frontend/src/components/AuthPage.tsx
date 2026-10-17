/**
 * v2.4 登录/注册对话框
 *
 * v3.6 改动：
 * - 字段下显示 hint（格式说明）
 * - 提交前本地校验（用户名 3+、密码 6+），避免无意义 422
 * - 切 tab / 改输入时清错
 * - 错误显示在对话框顶部（醒目），不挤在按钮上面
 */
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { X } from 'lucide-react'
import { useTranslation } from 'react-i18next'

export type AuthMode = 'login' | 'register'

interface AuthDialogProps {
  open: boolean
  authMode: AuthMode
  error: string
  isSubmitting: boolean
  notice: string
  password: string
  username: string
  /** v3.7：未登录整页态下隐藏关闭按钮 / 禁用遮罩点击关闭 */
  hideClose?: boolean
  onClose: () => void
  onAuthModeChange: (mode: AuthMode) => void
  onPasswordChange: (value: string) => void
  onSubmit: () => Promise<void>
  onUsernameChange: (value: string) => void
}

export function AuthDialog({
  open,
  authMode,
  error,
  isSubmitting,
  notice,
  password,
  username,
  hideClose = false,
  onClose,
  onAuthModeChange,
  onPasswordChange,
  onSubmit,
  onUsernameChange,
}: AuthDialogProps) {
  const { t } = useTranslation('auth')
  const { t: tc } = useTranslation('common')

  if (!open) return null

  // v3.6：本地字段校验
  const trimmedUsername = username.trim()
  const usernameError =
    authMode === 'register' && trimmedUsername.length > 0 && trimmedUsername.length < 3
      ? t('error_username_short')
      : ''
  const passwordError =
    password.length > 0 && password.length < 6 ? t('error_password_short') : ''
  const canSubmit =
    !isSubmitting && trimmedUsername.length >= 3 && password.length >= 6

  return (
    <div
      className="app-auth-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="app-auth-dialog-title"
      onClick={(event) => {
        // v3.7：hideClose 时禁用遮罩关闭
        if (hideClose) return
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <Card className="app-auth-dialog">
        {hideClose ? null : (
          <button
            type="button"
            className="app-auth-dialog-close"
            aria-label={tc('close')}
            onClick={onClose}
          >
            <X size={18} />
          </button>
        )}
        <span className="app-kicker">Rally</span>
        <h2 id="app-auth-dialog-title">{t('headline')}</h2>
        <p>{t('subhead')}</p>
        <div className="app-auth-tabs">
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
        {error ? (
          <div className="app-alert app-alert-error" role="alert">
            {error}
          </div>
        ) : null}
        {notice ? (
          <div className="app-alert app-alert-notice" role="status">
            {notice}
          </div>
        ) : null}
        <form
          className="app-auth-form"
          onSubmit={(event) => {
            event.preventDefault()
            void onSubmit()
          }}
        >
          <Label>
            {t('label_username')}
            <Input
              value={username}
              onChange={(event) => onUsernameChange(event.target.value)}
              placeholder={t('label_username_placeholder')}
              autoComplete="username"
              required
              aria-invalid={Boolean(usernameError)}
            />
            {authMode === 'register' ? (
              <span className="app-auth-hint">{t('hint_username')}</span>
            ) : null}
            {usernameError ? <span className="app-field-error">{usernameError}</span> : null}
          </Label>
          <Label>
            {t('label_password')}
            <Input
              type="password"
              value={password}
              onChange={(event) => onPasswordChange(event.target.value)}
              placeholder={t('label_password_placeholder')}
              autoComplete={authMode === 'login' ? 'current-password' : 'new-password'}
              required
              aria-invalid={Boolean(passwordError)}
            />
            {authMode === 'register' ? (
              <span className="app-auth-hint">{t('hint_password')}</span>
            ) : null}
            {passwordError ? <span className="app-field-error">{passwordError}</span> : null}
          </Label>
          <Button type="submit" disabled={!canSubmit}>
            {isSubmitting ? tc('submitting') : authMode === 'login' ? t('submit_login') : t('submit_register')}
          </Button>
        </form>
      </Card>
    </div>
  )
}

export function AuthLoading() {
  const { t } = useTranslation('common')
  return (
    <main className="app-shell app-auth-shell">
      <Card className="app-auth-card">
        <span className="app-kicker">Rally</span>
        <p>{t('loading')}</p>
      </Card>
    </main>
  )
}
