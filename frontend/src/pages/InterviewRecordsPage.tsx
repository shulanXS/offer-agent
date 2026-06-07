import { InterviewHeaderArt } from '@/components/InterviewHeaderArt'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useInterviewOptions } from '@/hooks/useInterviewConfiguration'
import { useInterviewSessionList } from '@/hooks/useInterviewSessionList'
import {
  INTERVIEW_LIST_LABELS,
  type InterviewListDisplayLabel,
  type InterviewSessionListItem,
} from '@/types/interviewSessionList'
import { CalendarDays, ChevronLeft, ChevronRight, Clock3, LoaderCircle } from 'lucide-react'
import {
  buildScoreRingPresentation,
  type ScoreRingPresentation,
} from '@/utils/evaluationScorePresentation'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'

interface InterviewRecordsPageProps {
  token: string
}

const PAGE_SIZE = 10
const ALL_FILTER_VALUE = 'all'

const STATUS_FILTER_OPTIONS: { value: '' | InterviewListDisplayLabel; label: string }[] = [
  { value: '', label: '全部状态' },
  { value: 'not_started', label: '未开始' },
  { value: 'in_progress', label: '面试中' },
  { value: 'evaluating', label: '评估中' },
  { value: 'pending_evaluation', label: '待评估' },
  { value: 'completed', label: '已结束' },
]

export function InterviewRecordsPage({ token }: InterviewRecordsPageProps) {
  const navigate = useNavigate()
  const { data, isLoading, error } = useInterviewSessionList(token)
  const { data: interviewOptions } = useInterviewOptions(token)

  const sessions = data ?? []
  const [roleFilter, setRoleFilter] = useState('')
  const [levelFilter, setLevelFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState<'' | InterviewListDisplayLabel>('')
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
    <div className="v2-records-page">
      <header className="v2-page-header v2-records-header">
        <div>
          <h2>面试记录</h2>
          <p>查看你的所有模拟面试记录，分析表现，持续进步。</p>
        </div>
        <InterviewHeaderArt />
      </header>

      {!isLoading && !error && sessions.length > 0 ? (
        <div className="v2-records-toolbar">
          <div className="v2-records-filters">
            <RecordFilterSelect
              ariaLabel="岗位筛选"
              value={roleFilter || ALL_FILTER_VALUE}
              onValueChange={(value) => setRoleFilter(value === ALL_FILTER_VALUE ? '' : value)}
              placeholder="全部岗位"
              options={[
                { value: ALL_FILTER_VALUE, label: '全部岗位' },
                ...(interviewOptions?.target_roles ?? []).map((item) => ({
                  value: item.value,
                  label: item.label,
                })),
              ]}
            />
            <RecordFilterSelect
              ariaLabel="难度筛选"
              value={levelFilter || ALL_FILTER_VALUE}
              onValueChange={(value) => setLevelFilter(value === ALL_FILTER_VALUE ? '' : value)}
              placeholder="全部难度"
              options={[
                { value: ALL_FILTER_VALUE, label: '全部难度' },
                ...(interviewOptions?.target_levels ?? []).map((item) => ({
                  value: item.value,
                  label: item.label,
                })),
              ]}
            />
            <RecordFilterSelect
              ariaLabel="状态筛选"
              value={statusFilter || ALL_FILTER_VALUE}
              onValueChange={(value) =>
                setStatusFilter(value === ALL_FILTER_VALUE ? '' : (value as InterviewListDisplayLabel))
              }
              placeholder="全部状态"
              options={STATUS_FILTER_OPTIONS.map((item) => ({
                value: item.value || ALL_FILTER_VALUE,
                label: item.label,
              }))}
            />
          </div>
        </div>
      ) : null}

      {isLoading ? (
        <Card className="v2-panel v2-records-loading">
          <LoaderCircle className="v2-eval-spinner" size={24} />
          <p>正在加载面试记录…</p>
        </Card>
      ) : null}

      {error ? <p className="v2-error v2-records-error">{readError(error)}</p> : null}

      {!isLoading && !error && sessions.length === 0 ? (
        <Card className="v2-panel v2-records-empty">
          <p>暂无面试记录。完成「创建面试」后将出现在这里。</p>
          <button type="button" className="v2-btn-confirm" onClick={() => navigate('/interviews/new')}>
            创建面试
          </button>
        </Card>
      ) : null}

      {!isLoading && !error && sessions.length > 0 && filteredSessions.length === 0 ? (
        <Card className="v2-panel v2-records-empty">
          <p>没有符合筛选条件的面试记录。</p>
          {hasActiveFilters ? (
            <button
              type="button"
              className="v2-text-button"
              onClick={() => {
                setRoleFilter('')
                setLevelFilter('')
                setStatusFilter('')
              }}
            >
              清除筛选
            </button>
          ) : null}
        </Card>
      ) : null}

      {!isLoading && !error && filteredSessions.length > 0 ? (
        <>
          <div className="v2-records-list">
            {paginatedSessions.map((session) => (
              <InterviewRecordRow key={session.id} session={session} onAction={() => navigate(session.action_path)} />
            ))}
          </div>
          <div className="v2-records-footer">
            <p className="v2-records-footnote">共 {filteredSessions.length} 条记录</p>
            {totalPages > 1 ? (
              <div className="v2-records-pagination">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={currentPage <= 1}
                  onClick={() => setPage((value) => Math.max(1, value - 1))}
                >
                  <ChevronLeft />
                  上一页
                </Button>
                <span className="v2-records-pagination-meta">
                  第 {currentPage} / {totalPages} 页
                </span>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={currentPage >= totalPages}
                  onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
                >
                  下一页
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
      <SelectTrigger className="v2-records-filter-select" aria-label={ariaLabel}>
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
  const roleLabel = session.target_role_label || session.target_role || '—'
  const levelLabel = session.target_level_label || '—'
  const title = session.title || roleLabel
  const scorePresentation = buildRecordScorePresentation(session)
  const statusLabel = INTERVIEW_LIST_LABELS[session.display_label]

  return (
    <Card className="v2-panel v2-record-row-card">
      <div className="v2-record-row">
        <div className="v2-record-score-col">
          <RecordScoreRing presentation={scorePresentation} />
          <span className="v2-record-score-label">得分</span>
        </div>

        <div className="v2-record-title-block">
          <h3>{title}</h3>
          <div className="v2-record-info-tags">
            <span className={`v2-record-difficulty v2-record-difficulty-${session.target_level || 'intermediate'}`}>
              {levelLabel}
            </span>
            <span className={`v2-record-status v2-record-status-${session.display_label}`}>{statusLabel}</span>
          </div>
        </div>

        <RecordMetric
          className="v2-record-metric-duration"
          icon={<Clock3 size={18} />}
          value={`${session.duration_minutes} 分钟`}
          label="测试时长"
        />
        <RecordMetric
          className="v2-record-metric-date"
          icon={<CalendarDays size={18} />}
          value={formatDateTime(session.session_at || session.created_at)}
          label="测试日期"
        />

        <div className="v2-record-row-actions">
          <button type="button" className="v2-record-outline-btn" onClick={onAction}>
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
    <div className={`v2-record-metric${className ? ` ${className}` : ''}`}>
      <div className="v2-record-metric-value">
        {icon}
        <strong>{value}</strong>
      </div>
      <span className="v2-record-metric-label">{label}</span>
    </div>
  )
}

function RecordScoreRing({ presentation }: { presentation: ScoreRingPresentation }) {
  if (presentation.score == null) {
    return (
      <div className="v2-record-score-ring empty" aria-label="暂无评分">
        <span className="v2-record-score-empty">—</span>
      </div>
    )
  }

  return (
    <div
      className={`v2-record-score-ring v2-record-score-ring-${presentation.tone}`}
      aria-label={`综合分 ${presentation.score}，满分 100`}
    >
      <svg viewBox="0 0 36 36" className="v2-record-score-svg" aria-hidden>
        <path
          className="v2-record-score-track"
          d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
        />
        <path
          className="v2-record-score-progress"
          strokeDasharray={`${presentation.progress}, 100`}
          d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
        />
      </svg>
      <div className="v2-record-score-center">
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
    statusFilter: '' | InterviewListDisplayLabel
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

function formatDateTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function readError(error: unknown) {
  return error instanceof Error ? error.message : '请求失败'
}
