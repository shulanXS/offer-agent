/**R7：登录后跳转目标路径管理。**

未登录访问受保护路由时把目标路径写入 sessionStorage，登录成功后跳转回原路径。
*/
import { useCallback } from 'react'

const RETURN_PATH_STORAGE_KEY = 'offer-agent-return-path'

export function useReturnUrl() {
  const read = useCallback((): string => {
    try {
      return sessionStorage.getItem(RETURN_PATH_STORAGE_KEY) || ''
    } catch {
      return ''
    }
  }, [])

  const clear = useCallback((): void => {
    try {
      sessionStorage.removeItem(RETURN_PATH_STORAGE_KEY)
    } catch {
      /* 忽略 */
    }
  }, [])

  return { read, clear }
}
