# 18 评估报告 Schema（B3）

关联：[`改进方案.md`](改进方案.md) §5 B3。

## 1. 报告根对象

```typescript
interface InterviewEvaluationReport {
  // 版本
  version: number

  // 报告来源
  source: "evidence_rule" | "agent_enriched" | "rule_minimal"

  // 综合摘要（一段话）
  summary: string

  // 候选人视角报告
  candidate_review: EvaluationCandidateReview

  // 综合得分（0-100）；部分覆盖时为已评分维度均分
  overall_score?: number | null

  // 覆盖度（0.0 - 1.0）
  coverage_rate: number

  // 置信度（0.0 - 1.0）
  overall_confidence: number

  // 覆盖详情
  coverage: EvaluationCoverage

  // 各维度评价（按 topic 拆分）
  competencies?: EvaluationCompetency[]

  // JD 要点验证
  jd_match?: EvaluationJdMatch | null

  // 逐题复盘
  question_reviews?: EvaluationQuestionReview[]

  // 练习建议
  practice_recommendations?: EvaluationPracticeRecommendation[]

  // 优势（列表）
  strengths: string[]

  // 风险项（列表）
  risks: string[]

  // 未验证项
  unverified_items: EvaluationUnverifiedItem[]

  // 模型信息（Provider/Model/调用次数）
  model_info?: Record<string, unknown> | null

  // B1：降级标记
  degraded?: boolean       // true 表示走了降级路径
  degraded_reason?: string  // 降级原因（evidence_driven_failed / agent_failed 等）
  degraded_message?: string // 对用户的友好提示
}
```

## 2. candidate_review 子结构

```typescript
interface EvaluationCandidateReview {
  // 标题（机器可读标签）
  headline: string

  // 综合摘要段落
  summary: string

  // 亮点（最多 3 条）
  highlights: EvaluationFeedbackEntry[]

  // 不足（最多 5 条）
  weaknesses: EvaluationFeedbackEntry[]

  // 建议（最多 5 条）
  suggestions: EvaluationFeedbackEntry[]

  // 覆盖说明文字（当部分覆盖时出现）
  coverage_note?: string

  // 得分标签（"综合得分" | "已评考察点均分"）
  overall_score_label?: string
}
```

## 3. competencies 各维度

```typescript
interface EvaluationCompetency {
  topic_id: string
  name: string
  dimension: string
  status: "verified" | "partially_verified" | "unverified"
  // 1-5 分；null 表示未评分
  score?: number | null
  confidence?: number
  // 证据引用
  evidence_references?: EvaluationEvidenceReference[]
  // 回答轮次（用于证据回放）
  answer_rounds?: EvaluationAnswerRound[]
  // Agent 点评（可为 null）
  evaluation_comment?: string
  // 风险项
  risks?: string[]
  // 优势项
  strengths?: string[]
}

interface EvaluationEvidenceReference {
  quote: string        // 候选人原话
  question?: string    // 对应追问
  answer?: string      // 回答内容
  sequence?: number   // 消息序列号
  matched_signal?: string  // 匹配到的考察信号
  polarity?: "positive" | "negative" | "neutral"
  strength?: number   // 0.0-1.0 置信度
}

interface EvaluationAnswerRound {
  sequence: number
  question: string
  answer: string
  evidence_items: EvaluationAnswerRoundEvidence[]
}
```

## 4. 评分映射

| competency.status | competency.score | 报告展示 |
| --- | --- | --- |
| verified | 4-5 | "表现较好" + 绿色 |
| verified | 3 | "有亮点待加强" + 橙色 |
| verified | 1-2 | "未达标" + 红色 |
| partially_verified | 任意 | "部分验证" + 黄色 |
| unverified | null | "讨论不足" + 灰色 |

综合分 `overall_score`（0-100）映射：
- 原始 1-5 分 → `score / 5 * 100`
- ≥3 分维度时 trim-mean（去最高最低各 1 个）
- 覆盖度 < 60% 时降权：`score * (0.8 + 0.2 * coverage)`

## 5. 降级路径

| 降级原因 | degraded_reason 值 | 建议 degraded_message |
| --- | --- | --- |
| 证据驱动评估失败 | `evidence_driven_failed` | "本场评估采用降级路径（极简模板），建议重新面试或联系管理员。" |
| Agent 增强失败 | `agent_enrichment_failed` | "评估增强步骤失败，基础报告已生成，建议以综合分为参考。" |
| 完全评估失败 | `evaluation_failed` | "评估生成失败，请稍后重试或联系管理员。" |

## 6. 来源与验证

- 字段定义位置：`frontend/src/types/interviewEvaluation.ts`
- 后端来源：`backend/app/services/interview_evaluation/report.py`
- 降级注入：`backend/app/services/interview_evaluation_service.py`
- 评分公式：`backend/app/services/interview_evaluation/aggregate.py`
