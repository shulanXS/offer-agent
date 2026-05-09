import type { InterviewEvaluation } from '../types'

type EvaluationViewProps = {
  title: string
  totalQuestionCount: number
  evaluation: InterviewEvaluation | null
  isLoading: boolean
  onOpenSession?: () => void
  onRestart: () => void
}

export function EvaluationView({
  title,
  totalQuestionCount,
  evaluation,
  isLoading,
  onOpenSession,
  onRestart,
}: EvaluationViewProps) {
  if (isLoading) {
    return (
      <div className="evaluation-loading">
        <div className="evaluation-loading-spinner" aria-hidden="true" />
        <h3>正式评估中，请稍等</h3>
        <p>系统正在汇总本轮问答、生成评分与改进建议，完成后会自动展示结果。</p>
      </div>
    )
  }

  if (!evaluation) {
    return (
      <div className="evaluation-empty">
        <h3>评估结果暂未生成</h3>
        <p>当前会话还没有可展示的评分结果，可以先返回对话记录继续完成面试。</p>
        {onOpenSession ? (
          <button className="primary" type="button" onClick={onOpenSession}>
            返回对话记录
          </button>
        ) : null}
      </div>
    )
  }

  return (
    <>
      <div className="evaluation-hero">
        <div className="evaluation-score">
          <span className="evaluation-score-label">总分</span>
          <strong>{evaluation.overall_score}</strong>
          <small>{evaluation.rating}</small>
        </div>
        <div className="evaluation-summary-card">
          <p className="evaluation-kicker">面试结果评估</p>
          <h3>{title}</h3>
          <p>{evaluation.summary}</p>
          <div className="evaluation-actions">
            {onOpenSession ? (
              <button className="ghost" type="button" onClick={onOpenSession}>
                查看对话记录
              </button>
            ) : null}
            <button className="primary" type="button" onClick={onRestart}>
              再来一场
            </button>
          </div>
        </div>
      </div>
      <div className="evaluation-grid">
        <article className="evaluation-panel">
          <h4>完成情况</h4>
          <p className="evaluation-metric">
            {evaluation.answered_questions} / {totalQuestionCount}
          </p>
          <p>已完成回答题数，可结合对话记录继续复盘每一题的回答展开程度。</p>
        </article>
        <article className="evaluation-panel">
          <h4>优势亮点</h4>
          <ul className="evaluation-list">
            {evaluation.strengths.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>
        <article className="evaluation-panel">
          <h4>改进建议</h4>
          <ul className="evaluation-list">
            {evaluation.improvement_suggestions.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>
      </div>
    </>
  )
}
