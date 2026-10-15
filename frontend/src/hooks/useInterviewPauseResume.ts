/**
 * v1.1: 暂停/恢复 hook
 *
 * 监听 document visibilitychange：
 *   离开页面（hidden）→ POST /api/interviews/{id}/pause
 *   回到页面（visible）→ POST /api/interviews/{id}/resume
 *
 * 后端 service 记录 paused_at，remaining_seconds 跳过这段。
 */
import { useEffect, useRef } from 'react'
import { requestJson } from '@/services/client'

interface UseInterviewPauseResumeOptions {
  sessionId: string
  token: string
  enabled: boolean
}

export function useInterviewPauseResume({ sessionId, token, enabled }: UseInterviewPauseResumeOptions) {
  const inFlight = useRef<Promise<unknown> | null>(null)

  function callPause(action: 'pause' | 'resume') {
    if (inFlight.current) return inFlight.current
    const p = requestJson(`/api/interviews/${sessionId}/${action}`, { method: 'POST' }, token, 5_000)
    inFlight.current = p
    p.finally(() => {
      if (inFlight.current === p) inFlight.current = null
    })
    return p
  }

  useEffect(() => {
    if (!enabled) return
    function handleVisibility() {
      const action = document.visibilityState === 'hidden' ? 'pause' : 'resume'
      callPause(action).catch(() => {
        // 静默：暂停失败不影响主流程
      })
    }
    document.addEventListener('visibilitychange', handleVisibility)
    return () => document.removeEventListener('visibilitychange', handleVisibility)
  }, [sessionId, token, enabled])
}
