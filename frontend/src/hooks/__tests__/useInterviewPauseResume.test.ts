/** v2.3: useInterviewPauseResume 排队不丢。
 *  模拟连续 hidden/visible/hidden，第二个 pause 不应被丢。
 *  使用 jsdom + 自定义 fetch mock。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'

import { useInterviewPauseResume } from '../useInterviewPauseResume'

type Call = { url: string; method: string }

const callLog: Call[] = []
const inFlight: { resolve?: () => void } = {}

beforeEach(() => {
  callLog.length = 0
  // 让 fetch 返回可控 promise：第一次返回 pending 直到 resolve
  global.fetch = vi.fn((url: string, init?: RequestInit) => {
    callLog.push({ url, method: (init?.method ?? 'GET').toUpperCase() })
    return new Promise((resolve) => {
      inFlight.resolve = () =>
        resolve(
          new Response(JSON.stringify({ ok: true }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        )
    })
  }) as unknown as typeof fetch
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('useInterviewPauseResume', () => {
  it('排队：连续 hidden/visible/hidden，最终能发出两个 pause', async () => {
    renderHook(() =>
      useInterviewPauseResume({
        sessionId: 'sess-1',
        token: 'tok',
        enabled: true,
      }),
    )

    // 第一次 hidden → pause
    await act(async () => {
      Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true })
      document.dispatchEvent(new Event('visibilitychange'))
    })

    // 立即第二次 visible → resume（被排队）
    await act(async () => {
      Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })
      document.dispatchEvent(new Event('visibilitychange'))
    })

    // 立即第三次 hidden → pause（也排队）
    await act(async () => {
      Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true })
      document.dispatchEvent(new Event('visibilitychange'))
    })

    // 释放第一次的飞行 promise
    await act(async () => {
      inFlight.resolve?.()
      // 等待 microtask
      await new Promise((r) => setTimeout(r, 0))
    })
    // 排队第一个（resume）
    await act(async () => {
      inFlight.resolve?.()
      await new Promise((r) => setTimeout(r, 0))
    })
    // 排队第二个（pause）
    await act(async () => {
      inFlight.resolve?.()
      await new Promise((r) => setTimeout(r, 0))
    })

    expect(callLog.length).toBeGreaterThanOrEqual(3)
    expect(callLog[0].url).toContain('/pause')
    expect(callLog[1].url).toContain('/resume')
    expect(callLog[2].url).toContain('/pause')
  })
})
