import { Bot, UserRound } from 'lucide-react'

export function InterviewerAvatar() {
  return (
    <div className="app-live-avatar app-live-avatar-interviewer" aria-hidden="true">
      <Bot size={18} strokeWidth={2.2} />
    </div>
  )
}

export function CandidateAvatar() {
  return (
    <div className="app-live-avatar app-live-avatar-candidate" aria-hidden="true">
      <UserRound size={18} strokeWidth={2.2} />
    </div>
  )
}
