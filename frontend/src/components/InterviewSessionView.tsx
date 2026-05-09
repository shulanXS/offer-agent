import type { ChatMessage } from '../types'

type InterviewSessionViewProps = {
  title: string
  messages: ChatMessage[]
  draftAnswer: string
  answeredCount: number
  totalQuestionCount: number
  completedQuestionCount: number
  progressPercent: number
  hasActiveSession: boolean
  isStreaming: boolean
  hasEvaluation: boolean
  currentUserAvatar: string
  messagesEndRef: React.RefObject<HTMLDivElement | null>
  onDraftAnswerChange: (value: string) => void
  onReply: () => void
  onFinish: () => void
  onOpenEvaluation: () => void
  formatMessageTime: (value: string) => string
}

export function InterviewSessionView({
  title,
  messages,
  draftAnswer,
  answeredCount,
  totalQuestionCount,
  completedQuestionCount,
  progressPercent,
  hasActiveSession,
  isStreaming,
  hasEvaluation,
  currentUserAvatar,
  messagesEndRef,
  onDraftAnswerChange,
  onReply,
  onFinish,
  onOpenEvaluation,
  formatMessageTime,
}: InterviewSessionViewProps) {
  return (
    <section className="interview-stage">
      <header className="interview-topbar">
        <div className="interview-title-block">
          <h2>{title}</h2>
        </div>
        <div className="interview-stats">
          <span className="interview-stat-label">
            已完成 {completedQuestionCount}/{totalQuestionCount} 题
          </span>
          <div className="interview-progress-track">
            <div className="interview-progress-fill" style={{ width: `${progressPercent}%` }} />
          </div>
          <strong className="interview-progress-text">{progressPercent}%</strong>
          {hasEvaluation ? (
            <button className="result-button" type="button" onClick={onOpenEvaluation}>
              查看评估
            </button>
          ) : null}
          <button className="finish-button" disabled={isStreaming || !hasActiveSession} onClick={onFinish}>
            结束面试
          </button>
        </div>
      </header>

      <section className="interview-thread">
        {messages.map((message) => (
          <article key={message.id} className={`interview-message interview-message-${message.role}`}>
            <div
              className={`interview-avatar ${message.role === 'assistant' ? 'interview-avatar-assistant' : 'interview-avatar-user'}`}
              aria-hidden="true"
            >
              <span>{message.role === 'assistant' ? 'A' : currentUserAvatar}</span>
            </div>
            <div className={`interview-bubble interview-bubble-${message.role}`}>
              {message.role === 'assistant' && !message.content ? (
                <div className="interview-thinking-bubble" aria-label="AI 思考中">
                  <span className="thinking-dot" />
                  <span className="thinking-dot" />
                  <span className="thinking-dot" />
                </div>
              ) : (
                <p>{message.content}</p>
              )}
              <small>{formatMessageTime(message.created_at)}</small>
            </div>
          </article>
        ))}
        <div ref={messagesEndRef} />
      </section>

      <footer className="interview-composer">
        <div className="interview-input-shell">
          <textarea
            rows={4}
            maxLength={500}
            value={draftAnswer}
            disabled={!hasActiveSession || isStreaming}
            onChange={(event) => onDraftAnswerChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                onReply()
              }
            }}
            placeholder={hasActiveSession ? '请输入你的回答，尽量说明你的思路、动作和结果' : '当前会话已结束'}
          />
          <div className="interview-input-meta">
            <span>本轮共回答 {answeredCount} 次</span>
            <span>{draftAnswer.length}/500</span>
          </div>
        </div>
        <button className="submit-answer-button" disabled={!hasActiveSession || isStreaming} onClick={onReply}>
          {isStreaming ? '提交中...' : '提交回答'}
        </button>
      </footer>
    </section>
  )
}
