import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export type AuthMode = 'login' | 'register'

interface AuthPageProps {
  authMode: AuthMode
  error: string
  isSubmitting: boolean
  notice: string
  password: string
  username: string
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
  onAuthModeChange,
  onPasswordChange,
  onSubmit,
  onUsernameChange,
}: AuthPageProps) {
  return (
    <main className="v2-shell v2-auth-shell">
      <Card className="v2-auth-card">
        <span className="v2-kicker">AI 面试官</span>
        <h1>专业模拟面试工作台</h1>
        <p>登录后管理简历，并进入新版面试配置与计划生成流程。</p>
        <div className="v2-auth-tabs">
          <Button variant={authMode === 'login' ? 'default' : 'outline'} onClick={() => onAuthModeChange('login')}>
            登录
          </Button>
          <Button variant={authMode === 'register' ? 'default' : 'outline'} onClick={() => onAuthModeChange('register')}>
            注册
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
            用户名
            <Input value={username} onChange={(event) => onUsernameChange(event.target.value)} required />
          </Label>
          <Label>
            密码
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
            {isSubmitting ? '提交中...' : authMode === 'login' ? '登录' : '注册并登录'}
          </Button>
        </form>
      </Card>
    </main>
  )
}

export function AuthLoading() {
  return (
    <main className="v2-shell v2-auth-shell">
      <Card className="v2-auth-card v2-loading-card">
        <span className="v2-kicker">AI 面试官</span>
        <h1>正在进入工作台</h1>
        <p>正在恢复登录状态。</p>
      </Card>
    </main>
  )
}
