/**R8：面试直播左侧 topic-bar 区域。*/
import { useTranslation } from 'react-i18next'

interface Props {
  currentTopicName?: string
}

export function InterviewLiveTopicBar({ currentTopicName }: Props) {
  const { t } = useTranslation('interview')
  return (
    <div className="app-live-topic-bar">
      <span className="app-live-topic-bar-label">{t('live_current_topic')}</span>
      <span className="app-live-topic-tag">{currentTopicName || '—'}</span>
    </div>
  )
}
