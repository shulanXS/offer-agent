import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Clock3, FileText, LogOut, Plus, PlusCircle, Zap } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { NavLink } from 'react-router-dom'
import { LanguageSwitcher } from '@/i18n/LanguageSwitcher'
import type { UserProfile } from '../types'

interface AppSidebarProps {
  user: UserProfile
  onLogout: () => void
  onOpenBilling: () => void
}

export function AppSidebar({ user, onLogout, onOpenBilling }: AppSidebarProps) {
  const { t, i18n } = useTranslation('sidebar')
  const isZh = i18n.language.startsWith('zh')
  return (
    <aside className="app-sidebar">
      <div className="app-brand">
        <span className="app-brand-mark">{isZh ? '面' : 'R'}</span>
        <div>
          <h1>{t('brand')}</h1>
          <p>{t('tagline')}</p>
        </div>
      </div>
      <div className="app-sidebar-lang-pill">
        <LanguageSwitcher />
      </div>
      <Card className="app-user-card">
        <CardContent className="grid gap-2 p-0">
          <Button className="app-user-logout" variant="ghost" size="sm" onClick={onLogout}>
            <LogOut />
            {t('logout')}
          </Button>
          <strong>{user.username}</strong>
          <div className="app-user-quota-row">
            {/* v2.3: quota_remaining 为 null 时显示「Unlimited」+ ⚡ */}
            {user.quota_remaining === null ? (
              <span className="app-user-quota-unlimited">
                <Zap size={14} aria-hidden /> {t('unlimited')}
              </span>
            ) : (
              <span>{t('quota_label', { count: user.quota_remaining })}</span>
            )}
            <button
              type="button"
              className="app-recharge-btn"
              onClick={onOpenBilling}
              aria-label={t('recharge')}
              title={t('recharge')}
            >
              <Plus size={14} />
            </button>
          </div>
          <Badge variant="secondary">{t(`tier_${user.tier || 'free'}`)}</Badge>
        </CardContent>
      </Card>
      <nav className="app-nav">
        <NavLink to="/resumes" end>
          <FileText />
          {t('nav_resumes')}
        </NavLink>
        <NavLink to="/interviews/new">
          <PlusCircle />
          {t('nav_create')}
        </NavLink>
        <NavLink to="/interviews" end>
          <Clock3 />
          {t('nav_records')}
        </NavLink>
      </nav>
      <div className="app-sidebar-footer" />
    </aside>
  )
}
