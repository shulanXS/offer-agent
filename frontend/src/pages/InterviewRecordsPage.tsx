import { InterviewHeaderArt } from '@/components/InterviewHeaderArt'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useInterviewOptions } from '@/hooks/useInterviewConfiguration'
import { useInterviewSessionList } from '@/hooks/useInterviewSessionList'
import {
  type InterviewSessionListItem,
} from '@/types/interviewSessionList'
import { bcp47ForIntl, useLocale } from '@/i18n/useLocale'
import { CalendarDays, ChevronLeft, ChevronRight, Clock3, LoaderCircle } from 'lucide-react'
import {
  buildScoreRingPresentation,
  type ScoreRingPresentation,
} from '@/utils/evaluationScorePresentation'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

interface InterviewRecordsPageProps {
  token: string
}

const PAGE_SIZE = 10
const ALL_FILTER_VALUE = 'all'

type StatusFilterValue = '' | 'not_started' | 'in_progress' | 'evaluating' | 'pending_evaluation' | 'completed'

const STATUS_FILTER_OPTIONS: { value: StatusFilterValue; label: string }[] = [
  { value: '', label: 'all' },
  { value: 'not_started', label: 'not_started' },
  { value: 'in_progress', label: 'in_progress' },
  { value: 'evaluating', label: 'evaluating' },
  { value: 'pending_evaluation', label: 'pending_evaluation' },
  { value: 'completed', label: 'completed' },
]

export function InterviewRecordsPage({ token }: InterviewRecordsPageProps) {
  const { t } = useTranslation('records')
  const { t: tc } = useTranslation('common')
  const navigate = useNavigate()
  const { data, isLoading, error } = useInterviewSessionList(token)
  const { data: interviewOptions } = useInterviewOptions(token)

  const sessions = data ?? []
  const [roleFilter, setRoleFilter] = useState('')
  const [levelFilter, setLevelFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusFilterValue>('')
  const [page, setPage] = useState(1)

  const filteredSessions = useMemo(
    () => filterSessions(sessions, { roleFilter, levelFilter, statusFilter }),
    [sessions, roleFilter, levelFilter, statusFilter],
  )

  const totalPages = Math.max(1, Math.ceil(filteredSessions.length / PAGE_SIZE))
  const currentPage = Math.min(page, totalPages)

  useEffect(() => {
    setPage(1)
  }, [roleFilter, levelFilter, statusFilter])

  useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages)
    }
  }, [page, totalPages])

  const paginatedSessions = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE
    return filteredSessions.slice(start, start + PAGE_SIZE)
  }, [currentPage, filteredSessions])

  const hasActiveFilters = Boolean(roleFilter || levelFilter || statusFilter)

  return (
    <div className="app-records-page">
      <header className="app-page-header app-records-header">
        <div>
          <h2>{t('records_title')}</h2>
          <p>{t('records_subtitle')}</p>
        </div>
        <InterviewHeaderArt />
      </header>

      {!isLoading && !error && sessions.length > 0 ? (
        <div className="app-records-toolbar">
          <div className="app-records-filters">
            <RecordFilterSelect
              ariaLabel={t('filter_role')}
              value={roleFilter || ALL_FILTER_VALUE}
              onValueChange={(value) => setRoleFilter(value === ALL_FILTER_VALUE ? '' : value)}
              placeholder={t('filter_all')}
              options={[
                { value: ALL_FILTER_VALUE, label: t('filter_all') },
                ...(interviewOptions?.target_roles ?? []).map((item) => ({
                  value: item.value,
                  label: item.label,
                })),
              ]}
            />
            <RecordFilterSelect
              ariaLabel={t('filter_level')}
              value={levelFilter || ALL_FILTER_VALUE}
              onValueChange={(value) => setLevelFilter(value === ALL_FILTER_VALUE ? '' : value)}
              placeholder={t('filter_all')}
              options={[
                { value: ALL_FILTER_VALUE, label: t('filter_all') },
                ...(interviewOptions?.target_levels ?? []).map((item) => ({
                  value: item.value,
                  label: item.label,
                })),
              ]}
            />
            <RecordFilterSelect
              ariaLabel={t('filter_status')}
              value={statusFilter || ALL_FILTER_VALUE}
              onValueChange={(value) =>
                setStatusFilter(value === ALL_FILTER_VALUE ? '' : (value as StatusFilterValue))
              }
              placeholder={t('filter_all')}
              options={STATUS_FILTER_OPTIONS.map((item) => ({
                value: item.value || ALL_FILTER_VALUE,
                label: t(`status_${item.label}`),
              }))}
            />
          </div>
        </div>
      ) : null}

      {isLoading ? (
        <Card className="app-panel app-records-loading">
          <LoaderCircle className="app-eval-spinner" size={24} />
          <p>{t('records_loading')}</p>
        </Card>
      ) : null}

      {error ? <p className="app-error app-records-error">{error instanceof Error ? error.message : tc('request_failed')}</p> : null}

      {!isLoading && !error && sessions.length === 0 ? (
        <Card className="app-panel app-records-empty">
          <p>{t('empty_records')}</p>
          <button type="button" className="app-btn-confirm" onClick={() => navigate('/interviews/new')}>
            {t('btn_create')}
          </button>
        </Card>
      ) : null}

      {!isLoading && !error && sessions.length > 0 && filteredSessions.length === 0 ? (
        <Card className="app-panel app-records-empty">
          <p>{t('empty_filtered')}</p>
          {hasActiveFilters ? (
            <button
              type="button"
              className="app-text-button"
              onClick={() => {
                setRoleFilter('')
                setLevelFilter('')
                setStatusFilter('')
              }}
            >
              {t('clear_filters')}
            </button>
          ) : null}
        </Card>
      ) : null}

      {!isLoading && !error && filteredSessions.length > 0 ? (
        <>
          <div className="app-records-list">
            {paginatedSessions.map((session) => (
              <InterviewRecordRow key={session.id} session={session} onAction={() => navigate(session.action_path)} />
            ))}
          </div>
          <div className="app-records-footer">
            <p className="app-records-footnote">{t('total_count', { count: filteredSessions.length })}</p>
            {totalPages > 1 ? (
              <div className="app-records-pagination">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={currentPage <= 1}
                  onClick={() => setPage((value) => Math.max(1, value - 1))}
                >
                  <ChevronLeft />
                  {t('btn_prev')}
                </Button>
                <span className="app-records-pagination-meta">
                  {t('page_meta', { current: currentPage, total: totalPages })}
                </span>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={currentPage >= totalPages}
                  onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
                >
                  {t('btn_next')}
                  <ChevronRight />
                </Button>
              </div>
            ) : null}
          </div>
        </>
      ) : null}
    </div>
  )
}

function RecordFilterSelect({
  ariaLabel,
  value,
  onValueChange,
  placeholder,
  options,
}: {
  ariaLabel: string
  value: string
  onValueChange: (value: string) => void
  placeholder: string
  options: { value: string; label: string }[]
}) {
  return (
    <Select value={value} onValueChange={onValueChange}>
      <SelectTrigger className="app-records-filter-select" aria-label={ariaLabel}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {options.map((item) => (
          <SelectItem key={item.value} value={item.value}>
            {item.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

function InterviewRecordRow({
  session,
  onAction,
}: {
  session: InterviewSessionListItem
  onAction: () => void
}) {
  const { t } = useTranslation('records')
  const locale = useLocale()
  const roleLabel = session.target_role_label || session.target_role || '—'
  const levelKey = `level_${session.target_level}`
  const levelLabel =
    session.target_level_label || (session.target_level ? t(levelKey as 'level_beginner') : '—')
  const title = session.title || roleLabel
  const scorePresentation = buildRecordScorePresentation(session)
  const statusKey = `status_${session.display_label}`
  const statusLabel = t(statusKey as 'status_not_started')

  return (
    <Card className="app-panel app-record-row-card">
      <div className="app-record-row">
        <div className="app-record-score-col">
          <RecordScoreRing presentation={scorePresentation} />
          <span className="app-record-score-label">{t('score_label_short')}</span>
        </div>

        <div className="app-record-title-block">
          <h3>{title}</h3>
          <div className="app-record-info-tags">
            <span className={`app-record-difficulty app-record-difficulty-${session.target_level || 'intermediate'}`}>
              {levelLabel}
            </span>
            <span className={`app-record-status app-record-status-${session.display_label}`}>{statusLabel}</span>
          </div>
        </div>

        <RecordMetric
          className="app-record-metric-duration"
          icon={<Clock3 size={18} />}
          value={t('common:minutes', { count: session.duration_minutes })}
          label={t('metric_duration')}
        />
        <RecordMetric
          className="app-record-metric-date"
          icon={<CalendarDays size={18} />}
          value={formatDateTime(session.session_at || session.created_at, locale)}
          label={t('metric_date')}
        />

        <div className="app-record-row-actions">
          <button type="button" className="app-record-outline-btn" onClick={onAction}>
            {session.action_label}
            <ChevronRight size={16} />
          </button>
        </div>
      </div>
    </Card>
  )
}

function RecordMetric({
  icon,
  value,
  label,
  className,
}: {
  icon: ReactNode
  value: string
  label: string
  className?: string
}) {
  return (
    <div className={`app-record-metric${className ? ` ${className}` : ''}`}>
      <div className="app-record-metric-value">
        {icon}
        <strong>{value}</strong>
      </div>
      <span className="app-record-metric-label">{label}</span>
    </div>
  )
}

function RecordScoreRing({ presentation }: { presentation: ScoreRingPresentation }) {
  const { t } = useTranslation('records')
  if (presentation.score == null) {
    return (
      <div className="app-record-score-ring empty" aria-label={t('score_empty')}>
        <span className="app-record-score-empty">—</span>
      </div>
    )
  }

  return (
    <div
      className={`app-record-score-ring app-record-score-ring-${presentation.tone}`}
      aria-label={t('score_aria_full', { score: presentation.score })}
    >
      <svg viewBox="0 0 36 36" className="app-record-score-svg" aria-hidden>
        <path
          className="app-record-score-track"
          d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
        />
        <path
          className="app-record-score-progress"
          strokeDasharray={`${presentation.progress}, 100`}
          d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
        />
      </svg>
      <div className="app-record-score-center">
        <strong>{presentation.score}</strong>
        {presentation.isPartial && presentation.total > 0 ? (
          <small>{presentation.scored}/{presentation.total}</small>
        ) : null}
      </div>
    </div>
  )
}

function buildRecordScorePresentation(session: InterviewSessionListItem): ScoreRingPresentation {
  return buildScoreRingPresentation({
    score: session.overall_score,
    totalTopicCount: session.total_topic_count,
    scoredTopicCount: session.scored_topic_count,
  })
}
function filterSessions(
  sessions: InterviewSessionListItem[],
  filters: {
    roleFilter: string
    levelFilter: string
    statusFilter: StatusFilterValue
  },
) {
  let items = [...sessions]
  if (filters.roleFilter) {
    items = items.filter((item) => item.target_role === filters.roleFilter)
  }
  if (filters.levelFilter) {
    items = items.filter((item) => item.target_level === filters.levelFilter)
  }
  if (filters.statusFilter) {
    items = items.filter((item) => item.display_label === filters.statusFilter)
  }
  items.sort((left, right) => {
    const leftTime = new Date(left.session_at || left.created_at).getTime()
    const rightTime = new Date(right.session_at || right.created_at).getTime()
    return rightTime - leftTime
  })
  return items
}

function formatDateTime(value: string, locale: 'zh' | 'en') {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString(bcp47ForIntl(locale), {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

