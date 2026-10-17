/** v2.3: createInterview service 透传 duration_minutes / interview_language 测试。
 *  用 vitest 风格；如未启用 vitest，可直接 `node --import tsx` 跑。
 *  此处主要做静态约定（避免 45 硬编码回归），不依赖 runtime fetch。
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

describe('interviewPlan service', () => {
  it('createInterview 不再硬编码 duration_minutes: 45', () => {
    const src = readFileSync(
      resolve(__dirname, '../interviewPlan.ts'),
      'utf8',
    )
    expect(src).not.toMatch(/duration_minutes:\s*45/)
  })

  it('createInterview 透传 payload（spread ...payload）', () => {
    const src = readFileSync(
      resolve(__dirname, '../interviewPlan.ts'),
      'utf8',
    )
    expect(src).toMatch(/\.\.\.payload/)
  })
})
