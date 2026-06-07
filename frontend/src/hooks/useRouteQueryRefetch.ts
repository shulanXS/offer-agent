import { useLocation } from 'react-router-dom'

function buildRouteKey(pathname: string, search: string) {
  return `${pathname}${search}`
}

/** 路由切换时用于 remount 当前页，清掉本地 state 并触发 React Query 重新挂载。 */
export function useRouteRemountKey() {
  const location = useLocation()
  return buildRouteKey(location.pathname, location.search)
}
