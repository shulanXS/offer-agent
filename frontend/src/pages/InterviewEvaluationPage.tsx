import { InterviewHeaderArt } from '@/components/InterviewHeaderArt'
import { Card } from '@/components/ui/card'
import { useInterviewEvaluationReport, useRetryInterviewEvaluation } from '@/hooks/useInterviewEvaluation'
import { useInterviewLearningContext } from '@/hooks/useInterviewLearning'
import type {
  LearningContextResponse,
  SessionComparison,
  SessionComparisonPoint,
  SessionComparisonTone,
} from '@/types/interviewLearning'
import type { UnifiedPracticeCard } from '@/types/interviewLearning'
import {
  buildUnifiedPracticeCards,
  shouldShowCrossSessionComparison,
} from '@/utils/buildUnifiedPracticeCards'
import {
  type EvaluationCompetency,
  type EvaluationCompetencyStatus,
  type EvaluationFeedbackEntry,
  type EvaluationFeedbackItem,
  type EvaluationJdMatch,
  type InterviewEvaluationReport,
} from '@/types/interviewEvaluation'
import {
  AlertTriangle,
  BarChart3,
  BriefcaseBusiness,
  ChevronLeft,
  ClipboardList,
  Code2,
  Layers3,
  LoaderCircle,
  Minus,
  MessageSquare,
  Network,
  Play,
  Route,
  Search,
  Sparkles,
  Target,
  ThumbsUp,
  TrendingDown,
  TrendingUp,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import {
  buildScoreRingPresentation,
  isLowCompetencyScore,
  resolveCompetencyStatusLabel,
  resolveCompetencyVisualTone,
} from '@/utils/evaluationScorePresentation'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

interface InterviewEvaluationPageProps {
  token: string
}

const DIMENSION_TAB_ICONS = [MessageSquare, Code2, Layers3, BriefcaseBusiness, Sparkles] as const
const COVERAGE_STATUS_LABELS: Record<EvaluationCompetencyStatus | 'low', string> = {
  verified: '已评',
  partially_verified: '部分评',
  unverified: '未评',
  low: '未达标',
}

export function InterviewEvaluationPage({ token }: InterviewEvaluationPageProps) {
  const { sessionId = '' } = useParams()
  const navigate = useNavigate()
  const { data, isPending, error, refetch } = useInterviewEvaluationReport(token, sessionId)
  const retryMutation = useRetryInterviewEvaluation(token, sessionId)

  const report = data?.evaluation ?? null
  // 仅首屏无报告时全页 loading；后台 refetch 不应遮挡已展示内容
  const isGenerating = (isPending || retryMutation.isPending) && !report

  async function handleRetry() {
    try {
      await retryMutation.mutateAsync()
    } catch {
      await refetch()
    }
  }

  return (
    <div className="v2-eval-page">
      <header className="v2-page-header v2-eval-header">
        <div>
          <button type="button" className="v2-eval-back-link" onClick={() => navigate('/interviews')}>
            <ChevronLeft size={16} />
            返回面试记录
          </button>
          <h2>面试评估</h2>
          <p>基于本场对话整理的可读复盘，帮你了解表现与主要不足。</p>
        </div>
        <InterviewHeaderArt />
      </header>

      {isGenerating ? (
        <Card className="v2-panel v2-eval-loading">
          <LoaderCircle className="v2-eval-spinner" size={28} />
          <h3>正在生成面试反馈</h3>
          <p>系统正在整理总结与各维度评价，请稍候。</p>
        </Card>
      ) : null}

      {!isGenerating && error ? (
        <Card className="v2-panel v2-eval-error">
          <h3>评估生成失败</h3>
          <p className="v2-error">{readError(error)}</p>
          <div className="v2-eval-actions">
            <button type="button" className="v2-btn-confirm" disabled={retryMutation.isPending} onClick={() => void handleRetry()}>
              重试评估
            </button>
          </div>
        </Card>
      ) : null}

      {!isGenerating && !error && report ? (
        <EvaluationReportView
          token={token}
          report={report}
          sessionId={sessionId}
          onReview={() => navigate(`/interviews/${sessionId}/live?review=1`)}
        />
      ) : null}

      {!isGenerating && !error && !report ? (
        <Card className="v2-panel v2-eval-error">
          <h3>暂无可展示的评估结果</h3>
          <p>请先完成面试并进入评估状态。</p>
          <button type="button" className="v2-btn-confirm" onClick={() => navigate(`/interviews/${sessionId}/live`)}>
            返回面试
          </button>
        </Card>
      ) : null}
    </div>
  )
}

function EvaluationReportView({
  token,
  report,
  sessionId,
  onReview,
}: {
  token: string
  report: InterviewEvaluationReport
  sessionId: string
  onReview: () => void
}) {
  const navigate = useNavigate()
  const { data: learningContext } = useInterviewLearningContext(token, sessionId, Boolean(report))
  const candidateReview = report.candidate_review
  const competencies = report.competencies ?? []
  const jdMatch = report.jd_match ?? null
  const scorePresentation = buildScorePresentation(report)
  const highlights = candidateReview?.highlights ?? []
  const weaknesses = candidateReview?.weaknesses ?? []
  const practiceCards = buildUnifiedPracticeCards(report, learningContext)
  const showCrossSession = shouldShowCrossSessionComparison(learningContext)

  return (
    <>
      <section className="v2-eval-section-wrap v2-eval-overview-section">
        <Card className="v2-panel v2-eval-overview-card">
          {scorePresentation.coverageNote ? (
            <p className={`v2-eval-coverage-note v2-eval-overview-top-note${scorePresentation.isPartial ? ' partial' : ''}`}>
              {scorePresentation.coverageNote}
            </p>
          ) : null}

          <div className="v2-eval-overview-grid">
            <div className="v2-eval-overview-score">
              <EvalScoreRing score={report.overall_score} />
              <p className="v2-eval-overview-score-label">综合得分</p>
            </div>

            <div className="v2-eval-overview-summary">
              <p className="v2-eval-overview-label">综合评价</p>
              <p className="v2-eval-overview-copy">{candidateReview?.summary}</p>
              {scorePresentation.total > 0 ? (
                <span className="v2-eval-overview-badge">
                  计划 {scorePresentation.total} 个方向 · 已评 {scorePresentation.scored} 个
                </span>
              ) : null}
            </div>

            {competencies.length ? (
              <div className="v2-eval-overview-coverage">
                <div className="v2-eval-overview-coverage-head">
                  <p className="v2-eval-overview-label">考察覆盖</p>
                  <span>
                    计划 {scorePresentation.total || competencies.length} 个方向 · 已评 {scorePresentation.scored} 个
                  </span>
                </div>
                <ul className="v2-eval-overview-coverage-list">
                  {competencies.map((competency) => {
                    const overviewStatus = resolveOverviewCoverageStatus(competency)
                    return (
                      <li key={competency.topic_id}>
                        <span className="v2-eval-overview-coverage-name">{competency.name}</span>
                        <div className="v2-eval-overview-coverage-bar-wrap">
                          <div
                            className={`v2-eval-overview-coverage-bar v2-eval-overview-coverage-bar-${overviewStatus}`}
                            style={{ width: `${coverageBarWidth(overviewStatus)}%` }}
                          />
                        </div>
                        <span className={`v2-eval-overview-coverage-status v2-eval-overview-coverage-status-${overviewStatus}`}>
                          {COVERAGE_STATUS_LABELS[overviewStatus]}
                        </span>
                      </li>
                    )
                  })}
                </ul>
              </div>
            ) : null}
          </div>
        </Card>
      </section>

      <SessionFeedbackSection highlights={highlights} weaknesses={weaknesses} />

      {showCrossSession && learningContext ? (
        <CrossSessionComparisonSection context={learningContext} />
      ) : null}
      {practiceCards.length ? (
        <PracticeRecommendationsSection
          cards={practiceCards}
          onPractice={(focusTopic) =>
            navigate('/interviews/new', { state: { prefilledFocusTopics: [focusTopic] } })
          }
        />
      ) : null}

      {competencies.length ? (
        <DimensionEvaluationSection key={sessionId} competencies={competencies} onReview={onReview} />
      ) : null}

      {jdMatch ? <JdMatchSection jdMatch={jdMatch} /> : null}

      <p className="v2-eval-footnote">会话 ID：{sessionId}</p>
    </>
  )
}

function EvalScoreRing({
  score,
}: {
  score: number | null | undefined
  isPartial?: boolean
}) {
  if (score == null) {
    return (
      <div className="v2-eval-score-ring empty" aria-label="暂无评分">
        <span className="v2-eval-score-empty">—</span>
      </div>
    )
  }

  const progress = Math.max(0, Math.min(100, score))
  const { tone } = buildScoreRingPresentation({ score })

  return (
    <div className={`v2-eval-score-ring v2-eval-score-ring-${tone}`} aria-hidden>
      <svg viewBox="0 0 36 36" className="v2-eval-score-svg" aria-hidden>
        <path
          className="v2-eval-score-track"
          d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
        />
        <path
          className="v2-eval-score-progress"
          strokeDasharray={`${progress}, 100`}
          d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
        />
      </svg>
      <div className="v2-eval-score-center">
        <strong>{score}</strong>
      </div>
    </div>
  )
}

const HIGHLIGHT_ITEM_ICONS = [Target, MessageSquare, Sparkles, Code2, Layers3] as const
const WEAKNESS_ITEM_ICONS = [Network, BarChart3, Search, Route, ClipboardList] as const

function SessionFeedbackSection({
  highlights,
  weaknesses,
}: {
  highlights: EvaluationFeedbackEntry[]
  weaknesses: EvaluationFeedbackEntry[]
}) {
  return (
    <section className="v2-eval-zone v2-eval-session-feedback-zone">
      <Card className="v2-panel v2-eval-session-feedback-panel">
        <div className="v2-eval-session-feedback-panel-head">
          <h3>本次反馈</h3>
          <p>基于本次面试表现，总结你的优势与不足，帮助你有针对性地提升。</p>
        </div>
        <div className="v2-eval-session-feedback-columns">
          <div className="v2-eval-session-feedback-column v2-eval-session-feedback-highlight">
            <div className="v2-eval-session-feedback-column-head">
              <span className="v2-eval-session-feedback-column-icon v2-eval-session-feedback-column-icon-highlight" aria-hidden>
                <ThumbsUp size={18} />
              </span>
              <h4>回答中的亮点</h4>
            </div>
            <FeedbackDetailList
              items={highlights}
              empty="暂无亮点。"
              tone="highlight"
              itemIcons={HIGHLIGHT_ITEM_ICONS}
            />
          </div>
          <div className="v2-eval-session-feedback-column v2-eval-session-feedback-weakness">
            <div className="v2-eval-session-feedback-column-head">
              <span className="v2-eval-session-feedback-column-icon v2-eval-session-feedback-column-icon-weakness" aria-hidden>
                <AlertTriangle size={18} />
              </span>
              <h4>主要不足</h4>
            </div>
            <FeedbackDetailList
              items={weaknesses}
              empty="暂无主要不足。"
              tone="weakness"
              itemIcons={WEAKNESS_ITEM_ICONS}
            />
          </div>
        </div>
      </Card>
    </section>
  )
}

function formatComparisonSummaryTag(summaryLine: string | undefined): string {
  if (!summaryLine?.trim()) {
    return ''
  }
  return summaryLine.replace(/^相比上场[：:]\s*/, '').trim()
}

function deriveComparisonSummaryTone(comparison: SessionComparison): SessionComparisonTone {
  const actionable = comparison.points.filter((point) => point.tone === 'better' || point.tone === 'worse')
  if (!actionable.length) {
    return 'same'
  }
  const hasBetter = actionable.some((point) => point.tone === 'better')
  const hasWorse = actionable.some((point) => point.tone === 'worse')
  if (hasBetter && hasWorse) {
    return 'same'
  }
  return hasBetter ? 'better' : 'worse'
}

function formatComparisonPointLine(point: SessionComparisonPoint): string {
  const headline = point.headline.trim()
  const detail = point.detail?.trim()
  if (detail) {
    return `${headline}，${detail}`
  }
  return headline
}

function CrossSessionComparisonSection({ context }: { context: LearningContextResponse }) {
  const comparison = context.session_comparison
  if (!comparison?.points.length) {
    return null
  }

  const coverage = comparison.discussed_coverage
  const summaryTag = formatComparisonSummaryTag(comparison.summary_line)
  const summaryTone = deriveComparisonSummaryTone(comparison)

  return (
    <section className="v2-eval-zone">
      <Card className="v2-panel v2-eval-cross-session-panel">
        <div className="v2-eval-cross-session-panel-head">
          <div className="v2-eval-cross-session-panel-head-row">
            <h3>与上一场对比</h3>
            {summaryTag ? (
              <span className={`v2-eval-cross-session-head-tag v2-eval-cross-session-head-tag-${summaryTone}`}>
                {summaryTag}
              </span>
            ) : null}
          </div>
          <p>
            已模拟 {context.session_count} 场 · {context.target_role_label || context.target_role} ·{' '}
            {context.interview_type_label || context.interview_type}。对比基于你的历史模拟，不影响本场评分。
          </p>
        </div>

        <div className="v2-eval-cross-session-body">
          <div className="v2-eval-cross-session-layout">
          <div className="v2-eval-cross-session-coverage-panel">
            <p className="v2-eval-cross-session-panel-title">{coverage?.label || '已考察方向'}</p>
            <div className="v2-eval-cross-session-coverage-compare">
              <div className="v2-eval-cross-session-coverage-side">
                <span className="v2-eval-cross-session-coverage-label">上一场</span>
                <strong className="v2-eval-cross-session-coverage-value">
                  {coverage?.baseline_count ?? 0}
                </strong>
                <span className="v2-eval-cross-session-coverage-unit">个</span>
              </div>
              <div className="v2-eval-cross-session-coverage-ring" aria-hidden="true">
                <TrendingUp size={22} />
              </div>
              <div className="v2-eval-cross-session-coverage-side current">
                <span className="v2-eval-cross-session-coverage-label">本场</span>
                <strong className="v2-eval-cross-session-coverage-value">
                  {coverage?.current_count ?? 0}
                </strong>
                <span className="v2-eval-cross-session-coverage-unit">个</span>
              </div>
            </div>
          </div>

          <div className="v2-eval-cross-session-changes-panel">
            <ul className="v2-eval-cross-session-change-list">
              {comparison.points.map((point) => (
                <li
                  key={`${point.category}-${point.headline}`}
                  className={`v2-eval-cross-session-change-item v2-eval-cross-session-change-item-${point.tone}`}
                >
                  <div className="v2-eval-cross-session-change-icon">
                    {point.tone === 'better' ? (
                      <TrendingUp size={16} />
                    ) : point.tone === 'worse' ? (
                      <TrendingDown size={16} />
                    ) : (
                      <Minus size={16} />
                    )}
                  </div>
                  <span className="v2-eval-cross-session-change-line">
                    {formatComparisonPointLine(point)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
          </div>
        </div>
      </Card>
    </section>
  )
}

function PracticeRecommendationsSection({
  cards,
  onPractice,
}: {
  cards: UnifiedPracticeCard[]
  onPractice: (focusTopic: string) => void
}) {
  return (
    <section className="v2-eval-zone">
      <Card className="v2-panel v2-eval-practice-panel">
        <div className="v2-eval-practice-panel-head">
          <h3>练习建议</h3>
          <p>基于本场薄弱项，给出可立即开始的重点练习方向。</p>
        </div>
        <div className="v2-eval-practice-body">
          <div className="v2-eval-practice-rows">
            {cards.map((card) => (
              <div key={card.id} className="v2-eval-practice-row">
                <div className="v2-eval-practice-row-copy">
                  <strong>{card.title}</strong>
                  <p>{card.summary}</p>
                </div>
                <button
                  type="button"
                  className="v2-btn-confirm v2-eval-practice-row-btn"
                  onClick={() => onPractice(card.focus_topic)}
                >
                  再练一次
                </button>
              </div>
            ))}
          </div>
        </div>
      </Card>
    </section>
  )
}

function FeedbackDetailList({
  items,
  empty,
  tone,
  itemIcons,
}: {
  items: EvaluationFeedbackEntry[]
  empty: string
  tone: 'highlight' | 'weakness'
  itemIcons: readonly LucideIcon[]
}) {
  if (!items.length) {
    return <p className="v2-eval-empty-copy">{empty}</p>
  }

  return (
    <ul className="v2-eval-feedback-detail-list">
      {items.map((item, index) => {
        const parsed = normalizeFeedbackEntry(item)
        const ItemIcon = itemIcons[index % itemIcons.length]
        return (
          <li key={`${parsed.title}-${index}`} className={`v2-eval-feedback-detail-item v2-eval-feedback-detail-item-${tone}`}>
            <span className={`v2-eval-feedback-detail-topic-icon v2-eval-feedback-detail-topic-icon-${tone}`} aria-hidden>
              <ItemIcon size={18} />
            </span>
            <div className="v2-eval-feedback-detail-copy">
              <strong>{parsed.title}</strong>
              <p>{parsed.body}</p>
            </div>
          </li>
        )
      })}
    </ul>
  )
}

function DimensionEvaluationSection({
  competencies,
  onReview,
}: {
  competencies: EvaluationCompetency[]
  onReview: () => void
}) {
  const [selectedTopicId, setSelectedTopicId] = useState(competencies[0]?.topic_id ?? '')
  const selectedCompetency = competencies.find((item) => item.topic_id === selectedTopicId) ?? competencies[0]

  if (!selectedCompetency) return null

  return (
    <section className="v2-eval-section-wrap v2-eval-dimensions">
      <Card className="v2-panel v2-eval-dimensions-panel">
        <div className="v2-eval-dimensions-panel-head">
          <h3>
            <Layers3 size={18} />
            各维度评价
          </h3>
          <p>各维度以状态和文字点评为主；上方综合分是本页唯一的数值参考。讨论不足的维度未计入综合分。</p>
        </div>

        <div className="v2-eval-dimensions-body">
          <div className="v2-eval-dimension-workspace">
            <div className="v2-eval-dimension-tabs" role="tablist" aria-label="各维度评价">
              {competencies.map((competency, index) => {
                const Icon = DIMENSION_TAB_ICONS[index % DIMENSION_TAB_ICONS.length]
                const active = competency.topic_id === selectedCompetency.topic_id
                const visualTone = resolveCompetencyVisualTone(competency.status, competency.score)
                const statusLabel = resolveCompetencyStatusLabel(competency.status, competency.score)
                return (
                  <button
                    key={competency.topic_id}
                    type="button"
                    role="tab"
                    aria-selected={active}
                    className={`v2-eval-dimension-tab${active ? ' active' : ''}`}
                    onClick={() => setSelectedTopicId(competency.topic_id)}
                  >
                    <Icon size={16} />
                    <span className="v2-eval-dimension-tab-name">{competency.name}</span>
                    <span className={`v2-eval-dimension-tab-status v2-eval-dimension-tab-status-${visualTone}`}>
                      <DimensionStatusDot status={competency.status} score={competency.score} />
                      {statusLabel}
                    </span>
                  </button>
                )
              })}
            </div>

            <DimensionDetailPanel competency={selectedCompetency} onReview={onReview} />
          </div>
        </div>
      </Card>
    </section>
  )
}

function DimensionDetailPanel({
  competency,
  onReview,
}: {
  competency: EvaluationCompetency
  onReview: () => void
}) {
  const evidenceRounds = buildEvidenceRounds(competency)
  const visualTone = resolveCompetencyVisualTone(competency.status, competency.score)
  const comment = competency.evaluation_comment?.trim()

  return (
    <div
      className="v2-eval-dimension-detail"
      role="tabpanel"
      aria-label={`${competency.name}评价详情`}
    >

      <div className={`v2-eval-dimension-comment-block v2-eval-dimension-comment-block-${visualTone}`}>
        <h4>维度评价</h4>
        <p>{comment || '暂无维度评价。'}</p>
      </div>

      {evidenceRounds.length ? (
        <div className="v2-eval-evidence-section">
          <div className="v2-eval-evidence-section-head">
            <h4>回答依据</h4>
            <p className="v2-eval-evidence-section-note">按对话先后顺序展示该主题下的全部问答。</p>
          </div>
          <ul className="v2-eval-evidence-rounds">
            {evidenceRounds.map((round) => (
              <li key={round.key} className="v2-eval-evidence-round">
                <div className="v2-eval-evidence-round-head">
                  <span className="v2-eval-evidence-round-index">第 {round.index} 轮</span>
                  <button type="button" className="v2-eval-evidence-play" onClick={onReview}>
                    <Play size={14} />
                    回放片段
                  </button>
                </div>
                {round.question ? (
                  <div className="v2-eval-evidence-qa-block">
                    <span className="v2-eval-evidence-qa-label">面试官</span>
                    <p>{round.question}</p>
                  </div>
                ) : null}
                <div className="v2-eval-evidence-qa-block">
                  <span className="v2-eval-evidence-qa-label">你的回答</span>
                  <p>{round.answer}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  )
}

function DimensionStatusDot({
  status,
  score,
}: {
  status: EvaluationCompetencyStatus
  score?: number | null
}) {
  const tone = resolveCompetencyVisualTone(status, score)
  return <span className={`v2-eval-status-dot v2-eval-status-dot-${tone}`} aria-hidden />
}

type JdMatchStatus = 'aligned' | 'risk' | 'unverified'

interface JdMatchListItem {
  key: string
  requirement: string
  topic_name?: string | null
  note?: string | null
  evidence_quotes?: string[]
  status: JdMatchStatus
}

const JD_MATCH_STATUS_LABELS: Record<JdMatchStatus, string> = {
  aligned: '已验证',
  risk: '有风险',
  unverified: '尚未验证',
}

function buildJdMatchListItems(jdMatch: EvaluationJdMatch): JdMatchListItem[] {
  return [
    ...jdMatch.verified_aligned.map((item) => ({
      key: `${item.topic_id ?? item.requirement}-aligned`,
      requirement: item.requirement,
      topic_name: item.topic_name,
      note: item.note,
      evidence_quotes: item.evidence_quotes,
      status: 'aligned' as const,
    })),
    ...jdMatch.verified_with_risk.map((item) => ({
      key: `${item.topic_id ?? item.requirement}-risk`,
      requirement: item.requirement,
      topic_name: item.topic_name,
      note: item.note,
      evidence_quotes: item.evidence_quotes,
      status: 'risk' as const,
    })),
    ...jdMatch.unverified.map((item) => ({
      key: `${item.topic_id ?? item.requirement}-unverified`,
      requirement: item.requirement,
      topic_name: item.topic_name,
      note: item.note,
      evidence_quotes: item.evidence_quotes,
      status: 'unverified' as const,
    })),
  ]
}

function JdMatchSection({ jdMatch }: { jdMatch: EvaluationJdMatch }) {
  const items = buildJdMatchListItems(jdMatch)
  const alignedCount = jdMatch.verified_aligned.length
  const riskCount = jdMatch.verified_with_risk.length
  const unverifiedCount = jdMatch.unverified.length

  return (
    <section className="v2-eval-section-wrap v2-eval-jd">
      <Card className="v2-panel v2-eval-jd-panel">
        <div className="v2-eval-jd-panel-head">
          <h3>
            <BriefcaseBusiness size={18} />
            本场 JD 要点验证
          </h3>
          <p>{jdMatch.summary}</p>
          {items.length ? (
            <div className="v2-eval-jd-stats">
              {alignedCount ? (
                <span className="v2-eval-jd-stat v2-eval-jd-stat-aligned">已验证 {alignedCount}</span>
              ) : null}
              {riskCount ? (
                <span className="v2-eval-jd-stat v2-eval-jd-stat-risk">有风险 {riskCount}</span>
              ) : null}
              {unverifiedCount ? (
                <span className="v2-eval-jd-stat v2-eval-jd-stat-unverified">尚未验证 {unverifiedCount}</span>
              ) : null}
            </div>
          ) : null}
          {items.length ? (
            <p className="v2-eval-jd-disclaimer">
              下列为本场计划对齐的 JD 要点。尚未验证表示本场未充分讨论或证据不足，不代表不符合岗位要求。
            </p>
          ) : null}
        </div>

        <div className="v2-eval-jd-body">
        {items.length ? (
          <ul className="v2-eval-jd-checklist">
            {items.map((item) => (
              <li key={item.key} className={`v2-eval-jd-checklist-item v2-eval-jd-checklist-item-${item.status}`}>
                <div className="v2-eval-jd-checklist-row">
                  <strong>{item.requirement}</strong>
                  <span className={`v2-eval-jd-status-badge v2-eval-jd-status-badge-${item.status}`}>
                    {JD_MATCH_STATUS_LABELS[item.status]}
                  </span>
                </div>
                {item.topic_name ? <span className="v2-eval-jd-topic">关联主题：{item.topic_name}</span> : null}
                {item.note ? <span className="v2-eval-jd-note">{item.note}</span> : null}
                {item.evidence_quotes?.length ? (
                  <blockquote className="v2-eval-jd-quote">{item.evidence_quotes[0]}</blockquote>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="v2-eval-empty-copy v2-eval-jd-empty-copy">{jdMatch.summary}</p>
        )}
        </div>
      </Card>
    </section>
  )
}

interface ScorePresentation {
  coverageNote: string
  scoreLabel: string
  isPartial: boolean
  total: number
  completed: number
  scored: number
  discussedOnly: number
  untouched: number
}

interface EvidenceRound {
  key: string
  index: number
  question: string
  answer: string
}

function buildEvidenceRounds(competency: EvaluationCompetency): EvidenceRound[] {
  if (competency.answer_rounds?.length) {
    return competency.answer_rounds.map((round, index) => ({
      key: `${round.sequence}:${round.question}:${round.answer}`,
      index: index + 1,
      question: round.question.trim(),
      answer: round.answer.trim(),
    }))
  }

  const roundMap = new Map<string, EvidenceRound>()

  for (const [index, item] of competency.evidence_references.entries()) {
    const answer = item.answer?.trim() || item.quote.trim()
    const question = item.question?.trim() ?? ''
    const sequence = item.sequence ?? index
    const roundKey = `${sequence}:${question}:${answer}`

    if (roundMap.has(roundKey)) {
      continue
    }

    roundMap.set(roundKey, {
      key: roundKey,
      index: roundMap.size + 1,
      question,
      answer,
    })
  }

  return Array.from(roundMap.values()).map((round, index) => ({
    ...round,
    index: index + 1,
  }))
}

function normalizeFeedbackEntry(entry: EvaluationFeedbackEntry): EvaluationFeedbackItem {
  if (typeof entry === 'string') {
    return parseFeedbackItem(entry)
  }
  const title = entry.title?.trim() ?? ''
  const body = entry.body?.trim() ?? ''
  if (title && body) {
    return { title, body }
  }
  if (title) {
    return { title, body: title }
  }
  return parseFeedbackItem(body)
}

function parseFeedbackItem(text: string): EvaluationFeedbackItem {
  const trimmed = text.trim()
  const bracketMatch = trimmed.match(/^「([^」]+)」(.+)?$/s)
  if (bracketMatch) {
    return {
      title: bracketMatch[1],
      body: (bracketMatch[2] ?? '').trim() || trimmed,
    }
  }

  const colonIndex = trimmed.indexOf('：')
  if (colonIndex > 0 && colonIndex <= 24) {
    return {
      title: trimmed.slice(0, colonIndex),
      body: trimmed.slice(colonIndex + 1).trim(),
    }
  }

  if (trimmed.length <= 18) {
    return { title: trimmed, body: trimmed }
  }

  const splitAt = trimmed.search(/[。；;]/)
  if (splitAt > 0 && splitAt <= 24) {
    return {
      title: trimmed.slice(0, splitAt),
      body: trimmed.slice(splitAt + 1).trim() || trimmed,
    }
  }

  return {
    title: trimmed.slice(0, 18),
    body: trimmed,
  }
}

function resolveOverviewCoverageStatus(competency: EvaluationCompetency): EvaluationCompetencyStatus | 'low' {
  if (competency.status === 'unverified' || competency.score == null) {
    return 'unverified'
  }
  if (isLowCompetencyScore(competency.status, competency.score)) {
    return 'low'
  }
  if (competency.status === 'partially_verified' || competency.score <= 3) {
    return 'partially_verified'
  }
  return 'verified'
}

function coverageBarWidth(status: EvaluationCompetencyStatus | 'low') {
  if (status === 'verified') return 100
  if (status === 'partially_verified') return 55
  if (status === 'low') return 28
  return 0
}

function readError(error: unknown) {
  return error instanceof Error ? error.message : '请求失败'
}

function buildScorePresentation(report: InterviewEvaluationReport): ScorePresentation {
  const coverage = report.coverage
  const completed = coverage?.completed_topic_count ?? 0
  const ring = buildScoreRingPresentation({
    score: report.overall_score,
    totalTopicCount: coverage?.total_topic_count,
    scoredTopicCount: coverage?.scored_topic_count,
    scoredTopicCountFallback: (report.competencies ?? []).filter((item) => item.score != null).length,
  })
  const { total, scored, isPartial } = ring
  const discussedFromCompetencies = (report.competencies ?? []).filter((item) => item.status !== 'unverified').length
  const discussed = Math.max(discussedFromCompetencies, scored)
  const discussedOnly = Math.max(0, discussed - scored)
  const untouched = Math.max(0, total - discussed)
  const coverageNote =
    (total > 0
      ? isPartial
        ? `本场计划 ${total} 个考察点，你聊到 ${discussed} 个，其中 ${scored} 个已有评分。综合分仅反映已评分内容，其余 ${total - scored} 个因讨论不足未计入，不代表能力不足。`
        : `本场计划 ${total} 个考察点，均已纳入综合分。`
      : '') || report.candidate_review?.coverage_note?.trim() || ''
  const scoreLabel =
    report.candidate_review?.overall_score_label?.trim() ||
    (isPartial ? '已评考察点均分' : '综合得分')

  return {
    coverageNote,
    scoreLabel,
    isPartial,
    total,
    completed,
    scored,
    discussedOnly,
    untouched,
  }
}
