// D3：评估页纯函数工具（无副作用，可独立测试）
import { Briefcase } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { BarChart3, ClipboardList, Code2, Layers3, MessageSquare, Network, Route, Search, Sparkles, Target } from 'lucide-react'
import type {
  EvaluationCompetency,
  EvaluationCompetencyStatus,
  EvaluationFeedbackEntry,
  EvaluationFeedbackItem,
  EvaluationJdMatch,
  InterviewEvaluationReport,
} from '@/types/interviewEvaluation'

export const DIMENSION_TAB_ICONS: readonly LucideIcon[] = [
  MessageSquare,
  Code2,
  Layers3,
  Briefcase,
  Sparkles,
]

export const HIGHLIGHT_ITEM_ICONS: readonly LucideIcon[] = [Target, MessageSquare, Sparkles, Code2, Layers3]
export const WEAKNESS_ITEM_ICONS: readonly LucideIcon[] = [Network, BarChart3, Search, Route, ClipboardList]

const COVERAGE_STATUS_I18N_KEYS: Record<EvaluationCompetencyStatus | 'low', string> = {
  verified: 'competency_status_verified',
  partially_verified: 'competency_status_partially_verified',
  unverified: 'competency_status_unverified',
  low: 'competency_status_low',
}

const JdMatchStatusI18nKeys: Record<'aligned' | 'risk' | 'unverified', string> = {
  aligned: 'jd_match_status_aligned',
  risk: 'jd_match_status_risk',
  unverified: 'jd_match_status_unverified',
}

export type OverviewCoverageStatus = EvaluationCompetencyStatus | 'low'

export function resolveOverviewCoverageStatus(competency: EvaluationCompetency): OverviewCoverageStatus {
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

function isLowCompetencyScore(status: EvaluationCompetencyStatus, score: number | null | undefined): boolean {
  if (score == null) return false
  // verified: 1-3 分均为 low；partially_verified: 同理
  if ((status === 'verified' || status === 'partially_verified') && score <= 3) return true
  return false
}

export function coverageBarWidth(status: OverviewCoverageStatus): number {
  if (status === 'verified') return 100
  if (status === 'partially_verified') return 55
  if (status === 'low') return 28
  return 0
}

export function coverageLabel(
  status: OverviewCoverageStatus,
  t: (key: string) => string = (key) => key,
): string {
  return t(COVERAGE_STATUS_I18N_KEYS[status])
}

export function jdStatusLabel(
  status: 'aligned' | 'risk' | 'unverified',
  t: (key: string) => string = (key) => key,
): string {
  return t(JdMatchStatusI18nKeys[status])
}

export interface JdMatchListItem {
  key: string
  requirement: string
  topic_name?: string | null
  note?: string | null
  evidence_quotes?: string[]
  status: 'aligned' | 'risk' | 'unverified'
}

export function buildJdMatchListItems(jdMatch: EvaluationJdMatch): JdMatchListItem[] {
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

export interface EvidenceRound {
  key: string
  index: number
  question: string
  answer: string
}

export function buildEvidenceRounds(competency: EvaluationCompetency): EvidenceRound[] {
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
    if (roundMap.has(roundKey)) continue
    roundMap.set(roundKey, { key: roundKey, index: roundMap.size + 1, question, answer })
  }
  return Array.from(roundMap.values()).map((round, index) => ({ ...round, index: index + 1 }))
}

export function normalizeFeedbackEntry(entry: EvaluationFeedbackEntry): EvaluationFeedbackItem {
  if (typeof entry === 'string') return parseFeedbackItem(entry)
  const title = entry.title?.trim() ?? ''
  const body = entry.body?.trim() ?? ''
  if (title && body) return { title, body }
  if (title) return { title, body: title }
  return parseFeedbackItem(body)
}

export function parseFeedbackItem(text: string): EvaluationFeedbackItem {
  const trimmed = text.trim()
  const bracketMatch = trimmed.match(/^「([^」]+)」(.+)?$/s)
  if (bracketMatch) {
    return { title: bracketMatch[1], body: (bracketMatch[2] ?? '').trim() || trimmed }
  }
  const colonIndex = trimmed.indexOf('：')
  if (colonIndex > 0 && colonIndex <= 24) {
    return { title: trimmed.slice(0, colonIndex), body: trimmed.slice(colonIndex + 1).trim() }
  }
  if (trimmed.length <= 18) return { title: trimmed, body: trimmed }
  const splitAt = trimmed.search(/[。；;]/)
  if (splitAt > 0 && splitAt <= 24) {
    return { title: trimmed.slice(0, splitAt), body: trimmed.slice(splitAt + 1).trim() || trimmed }
  }
  return { title: trimmed.slice(0, 18), body: trimmed }
}

export interface ScorePresentation {
  coverageNote: string
  scoreLabel: string
  isPartial: boolean
  total: number
  completed: number
  scored: number
  discussedOnly: number
  untouched: number
  degraded: boolean
  degradedReason?: string
  degradedMessage?: string
}

export function buildScorePresentation(report: InterviewEvaluationReport): ScorePresentation {
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
    degraded: Boolean(report.degraded),
    degradedReason: report.degraded_reason,
    degradedMessage: report.degraded_message,
  }
}

function buildScoreRingPresentation(input: {
  score: number | null | undefined
  totalTopicCount?: number
  scoredTopicCount?: number
  scoredTopicCountFallback?: number
}): { total: number; scored: number; isPartial: boolean } {
  const total = input.totalTopicCount ?? 0
  const scored = input.scoredTopicCount ?? input.scoredTopicCountFallback ?? 0
  const isPartial = total > 0 && scored < total
  return { total, scored, isPartial }
}
