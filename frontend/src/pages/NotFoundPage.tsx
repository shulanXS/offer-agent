// 5.9：路由 404 友好化
import { Link } from 'react-router-dom'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import i18n from '@/i18n'

export function NotFoundPage() {
  return (
    <div className="v2-notfound-page">
      <Card className="v2-notfound-card">
        <h1 className="v2-notfound-title">404</h1>
        <p className="v2-notfound-message">{i18n.t('common:not_found')}</p>
        <div className="v2-notfound-actions">
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
