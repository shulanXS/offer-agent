import type { LearningContextResponse, UnifiedPracticeCard } from '@/types/interviewLearning'
import type {
  EvaluationPracticeRecommendation,
  EvaluationQuestionReview,
  InterviewEvaluationReport,
} from '@/types/interviewEvaluation'

const MISSING_SIGNAL_GAP_PREFIX = '尚未覆盖考察信号：'
const PRACTICE_SIGNAL_PATTERN = /专项练习：如何清晰说明「([^」]+)」/
const MISSING_COVERAGE_ACTION_PATTERN = /补齐.*遗漏考察点/
const MAX_MISSING_SIGNALS_DISPLAY = 3

function buildFallbackSummary(
  reason: string,
  suggestedActions: string[] | undefined,
): string {
  const action = suggestedActions?.[0]?.trim()
  if (action) {
    const normalized = action.replace(/^围绕「[^」]+」/, '').trim()
    return normalized ? `建议${normalized.replace(/[。.]$/, '')}` : reason
  }
  return reason
}

function extractMissingSignalsFromReview(review: EvaluationQuestionReview): string[] {
  const signals: string[] = []
  const seen = new Set<string>()

  for (const gap of review.gaps_and_risks ?? []) {
    if (!gap.startsWith(MISSING_SIGNAL_GAP_PREFIX)) {
      continue
    }
    const signal = gap.slice(MISSING_SIGNAL_GAP_PREFIX.length).trim()
    if (signal && !seen.has(signal)) {
      seen.add(signal)
      signals.push(signal)
    }
  }

  for (const point of review.practice_points ?? []) {
    const match = point.match(PRACTICE_SIGNAL_PATTERN)
    const signal = match?.[1]?.trim()
    if (signal && !seen.has(signal)) {
      seen.add(signal)
      signals.push(signal)
    }
  }

  return signals
}

function buildReviewsByTopicId(
  reviews: EvaluationQuestionReview[] | undefined,
): Map<string, EvaluationQuestionReview> {
  const map = new Map<string, EvaluationQuestionReview>()
  for (const review of reviews ?? []) {
    map.set(review.topic_id, review)
  }
  return map
}

function collectMissingSignalsForRecommendation(
  item: EvaluationPracticeRecommendation,
  reviewsByTopicId: Map<string, EvaluationQuestionReview>,
): string[] {
  const topicIds = item.topic_ids?.length ? item.topic_ids : [item.topic_id]
  const signals: string[] = []
  const seen = new Set<string>()

  for (const topicId of topicIds) {
    const review = reviewsByTopicId.get(topicId)
    if (!review) {
      continue
    }
    for (const signal of extractMissingSignalsFromReview(review)) {
      if (!seen.has(signal)) {
        seen.add(signal)
        signals.push(signal)
      }
    }
  }

  return signals
}

export function formatMissingSignalsPracticeSummary(signals: string[]): string {
  if (!signals.length) {
    return ''
  }

  const shown = signals.slice(0, MAX_MISSING_SIGNALS_DISPLAY)
  const labels = shown.map((signal) => `「${signal}」`).join('')
  const hasMore = signals.length > shown.length

  return hasMore
    ? `建议补齐${labels}等遗漏考察点的回答要点`
    : `建议补齐${labels}遗漏考察点的回答要点`
}

function shouldUseMissingSignalsSummary(item: EvaluationPracticeRecommendation): boolean {
  const primaryAction = item.suggested_actions?.[0]?.trim() ?? ''
  if (MISSING_COVERAGE_ACTION_PATTERN.test(primaryAction)) {
    return true
  }

  const summary = item.summary?.trim() ?? ''
  return MISSING_COVERAGE_ACTION_PATTERN.test(summary)
}

function buildPracticeCardSummary(
  item: EvaluationPracticeRecommendation,
  reviewsByTopicId: Map<string, EvaluationQuestionReview>,
): string {
  if (shouldUseMissingSignalsSummary(item)) {
    const missingSignals = collectMissingSignalsForRecommendation(item, reviewsByTopicId)
    const missingSummary = formatMissingSignalsPracticeSummary(missingSignals)
    if (missingSummary) {
      return missingSummary
    }
  }

  return item.summary?.trim() || buildFallbackSummary(item.reason, item.suggested_actions)
}

export function buildUnifiedPracticeCards(
  report: InterviewEvaluationReport,
  _learningContext: LearningContextResponse | null | undefined,
): UnifiedPracticeCard[] {
  const recommendations = report.practice_recommendations ?? []
  if (!recommendations.length) {
    return []
  }

  const reviewsByTopicId = buildReviewsByTopicId(report.question_reviews)

  return recommendations.map((item) => ({
    id: item.id,
    title: item.title,
    focus_topic: item.focus_topic,
    summary: buildPracticeCardSummary(item, reviewsByTopicId),
  }))
}

export function shouldShowCrossSessionComparison(
  learningContext: LearningContextResponse | null | undefined,
): boolean {
  if (!learningContext?.cross_session_available) {
    return false
  }
  return Boolean(learningContext.session_comparison?.points?.length)
}

export function shouldShowLongTermActionSection(
  report: InterviewEvaluationReport,
  learningContext: LearningContextResponse | null | undefined,
): boolean {
  return (
    buildUnifiedPracticeCards(report, learningContext).length > 0 ||
    shouldShowCrossSessionComparison(learningContext)
  )
}
