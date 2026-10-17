// 5.9：路由 404 友好化
import { Link } from 'react-router-dom'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import i18n from '@/i18n'

export function NotFoundPage() {
  return (
    <div className="app-notfound-page">
      <Card className="app-notfound-card">
        <h1 className="app-notfound-title">404</h1>
        <p className="app-notfound-message">{i18n.t('common:not_found')}</p>
        <div className="app-notfound-actions">
          <Button asChild variant="default">
            <Link to="/resumes">{i18n.t('common:back_to_resumes')}</Link>
          </Button>
          <Button asChild variant="outline">
            <Link to="/interviews">{i18n.t('common:back_to_records')}</Link>
          </Button>
        </div>
      </Card>
    </div>
  )
}
