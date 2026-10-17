/**
 * v3.4 访客首页
 * - Hero（左右两栏）：品牌首屏 + 2×2 差异卡
 * - LiveUpdates：实时更新模块（题库 / 面试逻辑 / 评分模型）
 */
import { Hero } from './Hero'
import { LiveUpdates } from './LiveUpdates'

interface PublicHomeProps {
  onLoginClick: () => void
  onRegisterClick: () => void
}

export function PublicHome({ onRegisterClick }: PublicHomeProps) {
  return (
    <>
      <Hero onRegisterClick={onRegisterClick} />
      <LiveUpdates />
    </>
  )
}
