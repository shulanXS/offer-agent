import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Clock3, FileText, LogOut, PlusCircle } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import type { UserProfile } from '../types'

interface AppSidebarProps {
  user: UserProfile
  onLogout: () => void
}

export function AppSidebar({ user, onLogout }: AppSidebarProps) {
  return (
    <aside className="v2-sidebar">
      <div className="v2-brand">
        <span className="v2-brand-mark">AI</span>
        <div>
          <h1>AI 面试官</h1>
          <p>专业模拟面试工作台</p>
        </div>
      </div>
      <Card className="v2-user-card">
        <CardContent className="grid gap-2 p-0">
          <Button className="v2-user-logout" variant="ghost" size="sm" onClick={onLogout}>
            <LogOut />
            退出登录
          </Button>
          <strong>{user.username}</strong>
          <span>剩余额度：{user.quota_remaining}</span>
          <Badge variant="secondary">专业版</Badge>
        </CardContent>
      </Card>
      <nav className="v2-nav">
        <NavLink to="/resumes" end>
          <FileText />
          我的简历
        </NavLink>
        <NavLink to="/interviews/new">
          <PlusCircle />
          创建面试
        </NavLink>
        <NavLink to="/interviews" end>
          <Clock3 />
          面试记录
        </NavLink>
      </nav>
    </aside>
  )
}
