import type { InterviewQuestionPreview } from '../types'

type PreparingStageProps = {
  title: string
  openingMessage: string
  questions: InterviewQuestionPreview[]
  isPreparing: boolean
  isActivating: boolean
  canStart: boolean
  onBack: () => void
  onStart: () => void
}

export function PreparingStage({
  title,
  openingMessage,
  questions,
  isPreparing,
  isActivating,
  canStart,
  onBack,
  onStart,
}: PreparingStageProps) {
  return (
    <section className="preparing-stage">
      <div className="preparing-card">
        <p className="eyebrow">{isPreparing ? '题目生成中' : '题目准备完成'}</p>
        <h3>{title}</h3>
        <p className="preparing-copy">
          {isPreparing
            ? '系统正在根据你的简历、岗位和难度生成面试题，请稍候。'
            : '本轮题目已经生成完成，你可以先预览首题，再点击按钮正式开始面试。'}
        </p>
        <div className="preparing-preview">
          <span className="preparing-label">首题预览</span>
          <p>{openingMessage || '正在生成首题...'}</p>
        </div>
        <div className="preparing-question-list">
          <div className="preparing-question-list-header">
            <span className="preparing-label">全部题目预览</span>
            <span className="preparing-question-count">{questions.length > 0 ? `${questions.length} 道题` : '题目生成中'}</span>
          </div>
          {questions.length > 0 ? (
            questions.map((question, index) => (
              <details key={question.id || `${index}-${question.title}`} className="question-preview-item">
                <summary>
                  <span className="question-preview-order">Q{index + 1}</span>
                  <span className="question-preview-title">{question.title}</span>
                  <span className="question-preview-focus">{question.focus}</span>
                </summary>
                <div className="question-preview-body">
                  <p>{question.prompt}</p>
                  <small>追问方向：{question.follow_up_hint}</small>
                </div>
              </details>
            ))
          ) : (
            <div className="question-preview-empty">系统正在整理完整题单，稍后即可展开查看每一道题。</div>
          )}
        </div>
        <div className="preparing-actions">
          <button className="ghost" type="button" onClick={onBack} disabled={isPreparing}>
            返回调整
          </button>
          <button className="primary" type="button" onClick={onStart} disabled={!canStart}>
            {isActivating ? '进入中...' : '正式开始面试'}
          </button>
        </div>
      </div>
    </section>
  )
}
