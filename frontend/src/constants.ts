import type { SessionStatus } from './types'


export const DEFAULT_LANGUAGE = 'Java'
export const DEFAULT_DIFFICULTY_LEVEL = '入门'
export const DEFAULT_JOB_TITLE = '后端工程师'
export const DEFAULT_HIGHLIGHTS = 'Java, Redis, SQL, 接口设计'
export const DEFAULT_NOTICE = '这是一个脱敏教学版项目，保留了 CV 面试链路和流式体验。'

export const SESSION_STATUS_LABELS: Record<SessionStatus, string> = {
  preparing: '待开始',
  active: '进行中',
  completed: '已结束',
}
