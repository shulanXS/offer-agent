import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Clock3, FileText, LogOut, PlusCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { NavLink } from 'react-router-dom'
import { LanguageSwitcher } from '@/i18n/LanguageSwitcher'
import type { UserProfile } from '../types'

interface AppSidebarProps {
  user: UserProfile
  onLogout: () => void
}

export function AppSidebar({ user, onLogout }: AppSidebarProps) {
  const { t } = useTranslation('sidebar')
  return (
    <aside className="v2-sidebar">
      <div className="v2-brand">
        <span className="v2-brand-mark">AI</span>
        <div>
          <h1>{t('brand')}</h1>
          <p>{t('tagline')}</p>
        </div>
      </div>
      <Card className="v2-user-card">
        <CardContent className="grid gap-2 p-0">
          <Button className="v2-user-logout" variant="ghost" size="sm" onClick={onLogout}>
            <LogOut />
            {t('logout')}
          </Button>
          <strong>{user.username}</strong>
          <span>{t('quota_label', { count: user.quota_remaining })}</span>
          <Badge variant="secondary">{t('tier_label')}</Badge>
        </CardContent>
      </Card>
      <nav className="v2-nav">
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
      <div className="v2-sidebar-footer">
        <LanguageSwitcher />
      </div>
    </aside>
  )
}
