/**
 * v2.4 公开页 Layout - 未登录用户的整体外壳
 *
 * 包含：
 * - 顶部品牌栏（带语言切换 + 登录/注册按钮）
 * - 主内容区
 * - 底部简单信息
 */
import { useTranslation } from 'react-i18next'
import { LanguageSwitcher } from '@/i18n/LanguageSwitcher'
import { Button } from '@/components/ui/button'
import { LogIn, UserPlus } from 'lucide-react'
import type { ReactNode } from 'react'

interface PublicShellProps {
  children: ReactNode
  onLoginClick: () => void
  onRegisterClick: () => void
}

export function PublicShell({ children, onLoginClick, onRegisterClick }: PublicShellProps) {
  const { t, i18n } = useTranslation('common')
  const isZh = i18n.language.startsWith('zh')
  return (
    <div className="app-public-shell">
      <header className="app-public-header">
        <div className="app-public-header-inner">
          <div className="app-public-brand">
            <span className="app-brand-mark">{isZh ? '面' : 'R'}</span>
            <div>
              <strong>{t('brand_name')}</strong>
              <span>{t('brand_tagline')}</span>
            </div>
          </div>
          <div className="app-public-header-actions">
            <LanguageSwitcher />
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={onLoginClick}
            >
              <LogIn size={14} /> {t('nav_login')}
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={onRegisterClick}
            >
              <UserPlus size={14} /> {t('nav_register')}
            </Button>
          </div>
        </div>
      </header>
      <main className="app-public-main">{children}</main>
      <footer className="app-public-footer">
        <span>© {new Date().getFullYear()} {t('brand_name')}</span>
      </footer>
    </div>
  )
}
