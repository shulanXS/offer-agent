/**R8：单条面试消息气泡。*/
import { useTranslation } from 'react-i18next'
import { CandidateAvatar, InterviewerAvatar } from '../InterviewAvatars'
import type { ChatMessage } from '@/types'
import { bcp47ForIntl } from '@/i18n/useLocale'
import i18n from '@/i18n'

export function InterviewMessage({ message }: { message: ChatMessage }) {
  const { t } = useTranslation('interview')
  const isAssistant = message.role === 'assistant'
  const interviewerLabel = t('live_role_interviewer')
  const youLabel = t('live_role_you')
  const finalName = isAssistant ? interviewerLabel : youLabel
  const timestamp = formatMessageTime(message.created_at)
  const Avatar = isAssistant ? InterviewerAvatar : CandidateAvatar

  return (
    <article className={`app-live-thread ${isAssistant ? 'assistant' : 'user'}`}>
      <div className="app-live-thread-head">
        <Avatar />
        <div className="app-live-thread-meta">
          <strong>{finalName}</strong>
          {timestamp ? <time dateTime={message.created_at}>{timestamp}</time> : null}
        </div>
      </div>
      <div className="app-live-thread-content">
        <div className="app-live-bubble">{message.content}</div>
      </div>
    </article>
  )
}

function formatMessageTime(value: string) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const locale = (i18n.language || 'en').startsWith('zh') ? 'zh-CN' : 'en-US'
  return date.toLocaleTimeString(bcp47ForIntl(locale === 'zh-CN' ? 'zh' : 'en'), {
    timeZone: 'Asia/Shanghai',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}
