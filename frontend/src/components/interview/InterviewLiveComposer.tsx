/**R8：消息输入 composer。*/
import { useTranslation } from 'react-i18next'
import { SendHorizonal } from 'lucide-react'
import type React from 'react'

interface Props {
  draft: string
  canReply: boolean
  onDraftChange: (next: string) => void
  onSubmit: (event?: React.FormEvent) => void
  onKeyDown: (event: React.KeyboardEvent<HTMLTextAreaElement>) => void
}

export function InterviewLiveComposer({ draft, canReply, onDraftChange, onSubmit, onKeyDown }: Props) {
  const { t } = useTranslation('interview')
  return (
    <form className="app-live-composer" onSubmit={onSubmit}>
      <textarea
        value={draft}
        placeholder={t('live_composer_placeholder')}
        rows={4}
        disabled={!canReply}
        onChange={(event) => onDraftChange(event.target.value)}
        onKeyDown={onKeyDown}
      />
      <div className="app-live-composer-footer">
        <span className="app-live-composer-hint">Enter ↵</span>
        <button
          type="submit"
          className="app-btn-confirm app-live-send-btn"
          disabled={!canReply || !draft.trim()}
        >
          <SendHorizonal size={16} />
          {t('live_send')}
        </button>
      </div>
    </form>
  )
}
