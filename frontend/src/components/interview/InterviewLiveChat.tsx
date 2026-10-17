/**R8：聊天消息列表 + 流式打字状态。*/
import { useTranslation } from 'react-i18next'
import { LoaderCircle } from 'lucide-react'
import { Card } from '../ui/card'
import { InterviewerAvatar } from '../InterviewAvatars'
import { InterviewMessage } from './InterviewMessage'
import type { ChatMessage } from '@/types'

interface Props {
  messages: ChatMessage[]
  showReplyWaiting: boolean
  bottomRef: React.RefObject<HTMLDivElement | null>
}

export function InterviewLiveChat({ messages, showReplyWaiting, bottomRef }: Props) {
  const { t } = useTranslation('interview')
  return (
    <Card className="app-panel app-live-chat">
      <div className="app-live-message-list">
        {messages.map((message) => (
          <InterviewMessage key={message.id} message={message} />
        ))}
        {showReplyWaiting ? (
          <div className="app-live-streaming">
            <div className="app-live-thread-head">
              <InterviewerAvatar />
              <div className="app-live-streaming-copy">
                <LoaderCircle className="app-spin" size={16} />
                {t('live_typing')}
              </div>
            </div>
          </div>
        ) : null}
        <div ref={bottomRef} />
      </div>
    </Card>
  )
}
