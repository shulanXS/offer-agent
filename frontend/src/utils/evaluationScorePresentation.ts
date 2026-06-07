export type ScoreRingTone = 'high' | 'medium' | 'low'

/** 圆环颜色仅由分数决定，与是否评完所有考察点无关。 */
export const SCORE_RING_TIER = {
  high: { min: 80, label: '表现较好' },
  medium: { min: 60, label: '中等' },
  low: { min: 0, label: '待加强' },
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

export function resolveCompetencyStatusLabel(
  status: EvaluationCompetencyStatus,
  score: number | null | undefined,
): string {
  if (status === 'verified') {
    return '表现较好'
  }
  if (status === 'unverified') {
    return '讨论不足'
  }
  if (typeof score === 'number' && score <= 2) {
    return '明显不足'
  }
  if (score === 3) {
    return '仍有明显缺口'
  }
  return '有亮点待加强'
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
