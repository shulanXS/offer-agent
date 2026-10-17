/**R8：面试直播 header 子组件。*/
import { useTranslation } from 'react-i18next'
import { BarChart3, BriefcaseBusiness, Clock3, Code2 } from 'lucide-react'

interface Props {
  sessionTitle: string
  targetRoleLabel: string
  remainingTimeLabel: string
  topicProgressLabel: string
  isFinished: boolean
  needsActivate: boolean
  remainingSeconds: number | null
  isWrapUpZone: boolean
  includeAlgorithm: boolean
  canEnd: boolean
  isAlgoPanelOpen: boolean
  headerSubtitle: string
  onToggleAlgo: () => void
  onRequestFinish: () => void
}

export function InterviewLiveHeader({
  sessionTitle,
  targetRoleLabel,
  remainingTimeLabel,
  topicProgressLabel,
  isFinished,
  needsActivate,
  remainingSeconds,
  isWrapUpZone,
  includeAlgorithm,
  canEnd,
  isAlgoPanelOpen,
  headerSubtitle,
  onToggleAlgo,
  onRequestFinish,
}: Props) {
  const { t } = useTranslation('interview')
  return (
    <header className="app-live-header">
      <div className="app-live-header-top">
        <div className="app-live-header-title-row">
          <h2>{t('live_title')}</h2>
          <p className="app-live-header-subtitle">{headerSubtitle}</p>
        </div>
        {!needsActivate && !isFinished ? (
          <div className="app-live-header-actions">
            {includeAlgorithm ? (
              <button
                type="button"
                className="app-live-algo-btn"
                onClick={onToggleAlgo}
                aria-pressed={isAlgoPanelOpen}
              >
                <Code2 size={16} />
                {isAlgoPanelOpen ? t('algo_close') : t('algo_open')}
              </button>
            ) : null}
            <button
              type="button"
              className="app-live-end-btn"
              disabled={!canEnd}
              onClick={onRequestFinish}
            >
              <Clock3 size={16} />
              {t('live_end_btn')}
            </button>
          </div>
        ) : null}
      </div>

      {!needsActivate ? (
        <div className="app-live-header-meta" aria-label="Interview status">
          <div className="app-live-meta-item">
            <span className="app-live-meta-icon" aria-hidden="true">
              <BriefcaseBusiness size={18} />
            </span>
            <div>
              <span className="app-live-meta-label">{t('live_meta_role')}</span>
              <strong>{targetRoleLabel || sessionTitle || '—'}</strong>
            </div>
          </div>
          <div className="app-live-meta-item">
            <span className="app-live-meta-icon" aria-hidden="true">
              <BarChart3 size={18} />
            </span>
            <div>
              <span className="app-live-meta-label">{t('live_topic_progress')}</span>
              <strong>{topicProgressLabel}</strong>
            </div>
          </div>
          <div className="app-live-meta-item">
            <span className="app-live-meta-icon" aria-hidden="true">
              <Clock3 size={18} />
            </span>
            <div>
              <span className="app-live-meta-label">{t('live_remaining')}</span>
              <strong
                className={`app-live-countdown ${isWrapUpZone || remainingSeconds === 0 ? 'app-live-remaining-warning' : ''}`}
              >
                {remainingTimeLabel}
              </strong>
            </div>
          </div>
        </div>
      ) : null}
    </header>
  )
}
