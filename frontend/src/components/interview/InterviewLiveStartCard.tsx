/**R8：面试直播"等待激活"卡片。*/
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { LoaderCircle, MessageSquare } from 'lucide-react'
import { Card } from '../ui/card'

interface Props {
  isStarting: boolean
  showManualStartButton: boolean
  sessionId: string
  onActivate: () => void | Promise<void>
}

export function InterviewLiveStartCard({ isStarting, showManualStartButton, sessionId, onActivate }: Props) {
  const { t } = useTranslation('interview')
  const { t: tc } = useTranslation('common')
  const navigate = useNavigate()
  return (
    <Card className="app-panel app-live-start-card">
      {isStarting ? (
        <>
          <LoaderCircle className="app-spin" size={28} />
          <h3>{tc('loading')}</h3>
          <p>{t('live_loading')}</p>
        </>
      ) : (
        <>
          <MessageSquare size={28} />
          <h3>{t('live_activate_btn')}</h3>
          <p>{t('live_subtitle')}</p>
          <div className="app-live-start-actions">
            <button
              type="button"
              className="app-text-button"
              onClick={() => navigate(`/interviews/${sessionId}/plan`)}
            >
              {tc('back')}
            </button>
            {showManualStartButton ? (
              <button
                type="button"
                className="app-btn-confirm"
                onClick={() => void onActivate()}
              >
                {t('live_activate_btn')}
              </button>
            ) : null}
          </div>
        </>
      )}
    </Card>
  )
}
