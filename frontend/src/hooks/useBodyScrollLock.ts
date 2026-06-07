import { useEffect } from 'react'

let lockCount = 0

function lockBodyScroll() {
  lockCount += 1
  document.body.style.overflow = 'hidden'
}

function unlockBodyScroll() {
  lockCount = Math.max(0, lockCount - 1)
  if (lockCount === 0) {
    document.body.style.overflow = ''
  }
}

/** 多个弹窗/Loading 叠加时安全锁定页面滚动，避免 cleanup 互相覆盖导致无法滚动。 */
export function useBodyScrollLock(locked: boolean) {
  useEffect(() => {
    if (!locked) {
      return
    }

    lockBodyScroll()
    return () => {
      unlockBodyScroll()
    }
  }, [locked])
}
