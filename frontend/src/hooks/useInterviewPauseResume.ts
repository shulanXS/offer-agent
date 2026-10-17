/**
 * v2.3: 暂停/恢复 hook（带排队 + pagehide sendBeacon 兜底）
 *
 * 监听事件：
 *   - visibilitychange: 离开页面（hidden）→ pause；回到页面（visible）→ resume
 *   - pagehide: 浏览器关闭/切走，sendBeacon(pause) 兜底（visibilitychange 不触发）
 *
 * 行为：
 *   - inFlight: 当前正在飞行的 POST 请求
 *   - pendingActionRef: 等待飞行结束后立即执行的最新意图
 *   - 解决「inFlight 期间新 pause/resume 被丢弃」的问题
 */
import { useEffect, useRef } from 'react'
import { requestJson } from '@/services/client'

interface UseInterviewPauseResumeOptions {
  sessionId: string
  token: string
  enabled: boolean
}

type Action = 'pause' | 'resume'

export function useInterviewPauseResume({ sessionId, token, enabled }: UseInterviewPauseResumeOptions) {
  const inFlight = useRef<Promise<unknown> | null>(null)
  const pendingActionRef = useRef<Action | null>(null)
  // 防止 sendBeacon 与 POST 双发：去重哨兵
  const lastDispatchedActionRef = useRef<Action | null>(null)
  const lastDispatchedAtRef = useRef<number>(0)

  function callPause(action: Action): Promise<unknown> {
    if (inFlight.current) {
      // 记录最新意图，飞行结束后再执行
      pendingActionRef.current = action
      return inFlight.current
    }
    lastDispatchedActionRef.current = action
    lastDispatchedAtRef.current = Date.now()
    const p = requestJson(
      `/api/interviews/${sessionId}/${action}`,
      { method: 'POST' },
      token,
      5_000,
    )
    inFlight.current = p
    p.finally(() => {
      if (inFlight.current === p) inFlight.current = null
      const pending = pendingActionRef.current
      pendingActionRef.current = null
      if (pending && pending !== lastDispatchedActionRef.current) {
        // 串行执行最新意图
        void callPause(pending)
      }
    })
    return p
  }

  useEffect(() => {
    if (!enabled) return

    function handleVisibility() {
      const action: Action = document.visibilityState === 'hidden' ? 'pause' : 'resume'
      callPause(action).catch(() => {
        // 静默：暂停失败不影响主流程
      })
    }

    function handlePageHide() {
      // v2.3: 浏览器关闭/切后台时 visibilitychange 不一定触发。
      // 用 fetch keepalive 发 pause（sendBeacon 不支持自定义 Authorization）。
      // 同一动作 500ms 内去重，避免与 visibilitychange 双发。
      const now = Date.now()
      if (
        lastDispatchedActionRef.current === 'pause' &&
        now - lastDispatchedAtRef.current < 500
      ) {
        return
      }
      lastDispatchedActionRef.current = 'pause'
      lastDispatchedAtRef.current = now
      try {
        fetch(`${apiBase()}/api/interviews/${encodeURIComponent(sessionId)}/pause`, {
          method: 'POST',
          keepalive: true,
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ _pagehide: true }),
        }).catch(() => {})
      } catch {
        // 静默：pagehide 阶段无重试
      }
    }

    document.addEventListener('visibilitychange', handleVisibility)
    window.addEventListener('pagehide', handlePageHide)
    return () => {
      document.removeEventListener('visibilitychange', handleVisibility)
      window.removeEventListener('pagehide', handlePageHide)
    }
  }, [sessionId, token, enabled])
}

function apiBase(): string {
  try {
    // 与 client.withApiBase 同源（开发态走 Vite 代理）
    if (typeof window === 'undefined') return ''
    return window.location.origin
  } catch {
    return ''
  }
}
