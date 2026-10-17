export type ScoreRingTone = 'high' | 'medium' | 'low'

/** 圆环颜色仅由分数决定，与是否评完所有考察点无关。 */
export const SCORE_RING_TIER = {
  high: { min: 80, i18nKey: 'score_tier_high' },
  medium: { min: 60, i18nKey: 'score_tier_medium' },
  low: { min: 0, i18nKey: 'score_tier_low' },
} as const

export interface ScoreRingPresentation {
  score: number | null
  progress: number
  tone: ScoreRingTone
  isPartial: boolean
  scored: number
  total: number
}

import type { EvaluationCompetencyStatus } from '../types/interviewEvaluation'

type Translator = (key: string, options?: Record<string, unknown>) => string

export function resolveCompetencyStatusLabel(
  status: EvaluationCompetencyStatus,
  score: number | null | undefined,
  t: Translator = (key) => key,
): string {
  if (status === 'verified') {
    return t('competency_status_verified')
  }
  if (status === 'unverified') {
    return t('competency_status_unverified')
  }
  if (typeof score === 'number' && score <= 2) {
    return t('competency_status_low')
  }
  if (score === 3) {
    return t('competency_status_mid')
  }
  return t('competency_status_partial')
}

export function isLowCompetencyScore(
  status: EvaluationCompetencyStatus,
  score: number | null | undefined,
): boolean {
  return status === 'partially_verified' && typeof score === 'number' && score <= 2
}

export function resolveCompetencyVisualTone(
  status: EvaluationCompetencyStatus,
  score: number | null | undefined,
): EvaluationCompetencyStatus | 'low' {
  if (isLowCompetencyScore(status, score)) {
    return 'low'
  }
  return status
}

export function resolveScoreRingTone(score: number | null | undefined): ScoreRingTone {
  if (score == null) {
    return 'medium'
  }
  if (score >= SCORE_RING_TIER.high.min) {
    return 'high'
  }
  if (score >= SCORE_RING_TIER.medium.min) {
    return 'medium'
  }
  return 'low'
}

export function buildScoreRingPresentation(input: {
  score: number | null | undefined
  totalTopicCount?: number | null
  scoredTopicCount?: number | null
  scoredTopicCountFallback?: number
}): ScoreRingPresentation {
  const score = input.score ?? null
  const total = input.totalTopicCount ?? 0
  const scored = input.scoredTopicCount ?? input.scoredTopicCountFallback ?? 0
  const isPartial = total > 0 && scored < total
  const progress = score != null ? Math.max(0, Math.min(100, score)) : 0
  const tone = resolveScoreRingTone(score)

  return {
    score,
    progress,
    tone,
    isPartial,
    scored,
    total,
  }
}
