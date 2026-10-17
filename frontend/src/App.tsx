/**
 * v3.7 路由与壳层
 *
 * 重要改动：
 * - 未登录态 = 首页（PublicHome / PublicShell）+ 模态登录对话框。
 *   首页（HOMEPAGE）= 营销着陆页 ≠ 占位卡片（PublicPagePlaceholder）——
 *   /resumes /interviews/new /interviews 等已登录专属路由直接进首页，不再渲染占位。
 * - 401 处理收敛：只清 token，由 AppRoutes 自然落到登录页（不再 setIsAuthDialogOpen + navigate），
 *   避免登录成功后被旧 token 残留或并发请求的 401 误踢。
 */
import { useEffect, useRef, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { AppSidebar } from './components/AppSidebar'
import { AuthDialog, AuthLoading, type AuthMode } from './components/AuthPage'
import { BillingPanel } from './components/BillingPanel'
import { PublicHome } from './components/PublicHome'
import { PublicShell } from './components/PublicShell'
import { InterviewConfigurationPage } from './pages/InterviewConfigurationPage'
import { InterviewEvaluationPage } from './pages/InterviewEvaluationPage'
import { InterviewLivePage } from './pages/InterviewLivePage'
import { InterviewPlanPage } from './pages/InterviewPlanPage'
import { InterviewRecordsPage } from './pages/InterviewRecordsPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { ResumesPage } from './pages/ResumesPage'
import { BillingReturnPage } from './pages/BillingReturnPage'
import { getMe, login, register } from './services/auth'
import { deleteResume, extractResume, getResume, listResumes } from './services/resume'
import type { AuthResponse, ResumeSummary, UserProfile } from './types'
import { useRouteRemountKey } from './hooks/useRouteQueryRefetch'
import {
    createProcessingResume,
    loadPersistedProcessingIds,
    MAX_RESUME_COUNT,
    persistProcessingIds,
    replaceResume,
    toResumeCardItem,
    toResumeSummary,
    type ResumeCardItem,
} from './utils/resume'
import { getStoredToken, registerUnauthorizedHandler, setStoredToken, ApiError } from './services/client'
import i18n from './i18n'
import './App.css'

const RETURN_PATH_STORAGE_KEY = 'offer-agent-return-path'

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}

function AppRoutes() {
  const location = useLocation()
  const navigate = useNavigate()
  const routeRemountKey = useRouteRemountKey()
  const initialToken = getStoredToken()
  const [token, setToken] = useState(initialToken)
  const [authMode, setAuthMode] = useState<AuthMode>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [user, setUser] = useState<UserProfile | null>(null)
  const [resumes, setResumes] = useState<ResumeCardItem[]>([])
  const [selectedResume, setSelectedResume] = useState<ResumeSummary | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [isLoading, setIsLoading] = useState(Boolean(initialToken))
  const [isSubmittingAuth, setIsSubmittingAuth] = useState(false)
  const [isAuthDialogOpen, setIsAuthDialogOpen] = useState(false)
  const [isExtracting, setIsExtracting] = useState(false)
  const [deletingResumeId, setDeletingResumeId] = useState('')
  const [isBillingOpen, setIsBillingOpen] = useState(false)
  const [authError, setAuthError] = useState('')
  const processingIdsRef = useRef<string[]>(loadPersistedProcessingIds())

  // 401 处理：仅清 token；UI 由 user/token 状态自然收敛到登录页。
  // 不在此处 navigate/setIsAuthDialogOpen，避免：
  // 1) 旧 token 残留导致登录成功后被并发请求的 401 误踢
  // 2) 与多 tab 共享 localStorage 时的状态竞争
  useEffect(() => {
    registerUnauthorizedHandler(() => {
      clearAuth({ skipNavigate: true })
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!token) {
      // 无 token：isLoading 初始为 false，未登录态分支自然渲染登录页
      return
    }

    let active = true
    // eslint-disable-next-line react-hooks/set-state-in-effect -- 拉取数据进入 loading 是 fetch-on-mount 标准模式
    setIsLoading(true)
    Promise.all([getMe(token), listResumes(token)])
      .then(([profile, resumeList]) => {
        if (!active) return
        setUser(profile)
        setResumes(resumeList.map(toResumeCardItem))
        setError('')
      })
      .catch((err: unknown) => {
        if (!active) return
        // 401 已被 registerUnauthorizedHandler 清掉 token，
        // 走到这里说明是非 401 的拉取失败：保留登录态但报错。
        if (!(err instanceof ApiError) || err.status !== 401) {
          setError(readError(err))
        }
      })
      .finally(() => {
        if (active) setIsLoading(false)
      })

    return () => {
      active = false
    }
  }, [token])

  function clearAuth(options: { skipNavigate?: boolean } = {}) {
    setStoredToken('')
    setToken('')
    setUser(null)
    setResumes([])
    setSelectedResume(null)
    setIsLoading(false)
    if (!options.skipNavigate) {
      navigate('/')
    }
  }

  function openAuthDialog(mode: AuthMode = 'login') {
    setAuthMode(mode)
    setAuthError('')
    setNotice('')
    setIsAuthDialogOpen(true)
  }

  function closeAuthDialog() {
    setIsAuthDialogOpen(false)
    setAuthError('')
    setNotice('')
  }

  async function handleAuthSubmit() {
    setAuthError('')
    setNotice('')
    setIsSubmittingAuth(true)
    try {
      const response: AuthResponse =
        authMode === 'login' ? await login(username.trim(), password) : await register(username.trim(), password)
      setStoredToken(response.access_token)
      setToken(response.access_token)
      setUser(response.user)
      setPassword('')
      setNotice(i18n.t(`auth:notice_${authMode}`))
      // v3.8：登录成功直接关模态，不再停留 1.5s 展示 notice。
      // 原因：notice 主要是"注册成功，请登录"这种状态回执，
      // 登录后用户应立即进入工作台；notice 通过侧栏/工作台顶部 toast
      // 表达更合适（当前未实现 toast，故不展示）。
      setIsAuthDialogOpen(false)

      const returnPath = readStoredReturnPath()
      if (returnPath) {
        clearStoredReturnPath()
        navigate(returnPath, { replace: true })
      } else {
        navigate('/resumes')
      }
    } catch (err) {
      setAuthError(readError(err))
    } finally {
      setIsSubmittingAuth(false)
    }
  }

  async function handleResumeSelect(resumeId: string) {
    const target = resumes.find((resume) => resume.id === resumeId)
    if (target?.parse_status === 'processing') return

    setError('')
    if (target) {
      setSelectedResume(target)
    }
    try {
      const resume = await getResume(token, resumeId)
      setSelectedResume(resume)
      setResumes((prev) => replaceResume(prev, resume))
    } catch (err) {
      setError(readError(err))
    }
  }

  async function handleResumeUpload(file: File | null) {
    if (!file) return
    if (resumes.filter((resume) => resume.parse_status === 'ready').length >= MAX_RESUME_COUNT) {
      setError(i18n.t('resumes:max_count_error', { max: MAX_RESUME_COUNT }))
      return
    }

    const processingResume = createProcessingResume(file.name)
    setError('')
    setIsExtracting(true)
    setResumes((prev) => [processingResume, ...prev])
    persistProcessingIds([processingResume.id, ...processingIdsRef.current])

    try {
      const result = await extractResume(token, file)
      setResumes((prev) => prev.filter((resume) => resume.id !== processingResume.id))
      if (result.id) {
        const resume = toResumeSummary(result)
        setResumes((prev) => replaceResume(prev, resume))
        setSelectedResume(resume)
      } else {
        await reloadResumes()
      }
    } catch (err) {
      setResumes((prev) => prev.filter((resume) => resume.id !== processingResume.id))
      setError(readError(err))
    } finally {
      setIsExtracting(false)
      const next = processingIdsRef.current.filter((id) => id !== processingResume.id)
      persistProcessingIds(next)
    }
  }

  async function handleResumeDelete(resume: ResumeCardItem) {
    if (resume.parse_status === 'processing') {
      return
    }

    setError('')
    setDeletingResumeId(resume.id)
    try {
      await deleteResume(token, resume.id)
      setResumes((prev) => prev.filter((item) => item.id !== resume.id))
      if (selectedResume?.id === resume.id) {
        setSelectedResume(null)
      }
    } catch (err) {
      setError(readError(err))
    } finally {
      setDeletingResumeId('')
    }
  }

  async function reloadResumes() {
    const resumeList = await listResumes(token)
    setResumes(resumeList.map(toResumeCardItem))
    if (processingIdsRef.current.length > 0) {
      const serverIds = new Set(resumeList.map((r) => r.id))
      const stale = processingIdsRef.current.filter((id) => serverIds.has(id))
      if (stale.length !== processingIdsRef.current.length) {
        const next = processingIdsRef.current.filter((id) => !serverIds.has(id))
        processingIdsRef.current = next
        persistProcessingIds(next)
      }
    }
  }

  useEffect(() => {
    if (token && user && processingIdsRef.current.length > 0) {
      void reloadResumes()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, user?.id])

  // v3.8：未登录态下，已登录专属 URL（/resumes /interviews/* 等）一律跳回首页。
  // 例外：/billing/return 由独立的 BillingReturnPage 渲染，不在此重定向。
  useEffect(() => {
    if (!token || !user) {
      if (location.pathname !== '/' && location.pathname !== '/billing/return') {
        navigate('/', { replace: true })
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, user?.id, location.pathname])

  // 加载中（已登录时拉取用户信息）
  if (isLoading && token && !user) {
    return <AuthLoading />
  }

  // === v2.5：Stripe 回调落地页（独立路由，不受登录态约束） ===
  if (location.pathname === '/billing/return') {
    return <BillingReturnPage />
  }

  // === 已登录态：完整应用 ===
  if (user) {
    return (
      <main className="app-shell">
        <AppSidebar user={user} onLogout={clearAuth} onOpenBilling={() => setIsBillingOpen(true)} />
        <section className="app-content" key={routeRemountKey}>
          <Routes location={location}>
            <Route path="/" element={<Navigate to="/resumes" replace />} />
            <Route
              path="/resumes"
              element={
                <ResumesPage
                  error={error}
                  resumes={resumes}
                  selectedResume={selectedResume}
                  isExtracting={isExtracting}
                  deletingResumeId={deletingResumeId}
                  onResumeSelect={handleResumeSelect}
                  onResumeUpload={handleResumeUpload}
                  onResumeDelete={handleResumeDelete}
                />
              }
            />
            <Route
              path="/interviews/new"
              element={<InterviewConfigurationPage token={token} resumes={resumes} selectedResume={selectedResume} />}
            />
            <Route path="/interviews/:sessionId/plan" element={<InterviewPlanPage token={token} />} />
            <Route path="/interviews/:sessionId/live" element={<InterviewLivePage token={token} />} />
            <Route path="/interviews/:sessionId/evaluation" element={<InterviewEvaluationPage token={token} />} />
            <Route path="/interviews" element={<InterviewRecordsPage token={token} />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </section>
        <BillingPanel
          open={isBillingOpen}
          onClose={() => setIsBillingOpen(false)}
          token={token}
          onRecharged={async () => {
            try {
              const fresh = await getMe(token)
              setUser(fresh)
            } catch (err) {
              console.warn('useBillingRecharge refresh failed', err)
            }
          }}
        />
      </main>
    )
  }

  // === 未登录态：首页 + 模态登录（v3.7 移除 PublicPagePlaceholder；已登录专属路由统一落到首页） ===
  return (
    <>
      <PublicShell
        onLoginClick={() => openAuthDialog('login')}
        onRegisterClick={() => openAuthDialog('register')}
      >
        <PublicHome
          onLoginClick={() => openAuthDialog('login')}
          onRegisterClick={() => openAuthDialog('register')}
        />
      </PublicShell>
      <AuthDialog
        open={isAuthDialogOpen}
        authMode={authMode}
        error={authError}
        isSubmitting={isSubmittingAuth}
        notice={notice}
        password={password}
        username={username}
        onClose={closeAuthDialog}
        onAuthModeChange={setAuthMode}
        onPasswordChange={setPassword}
        onSubmit={handleAuthSubmit}
        onUsernameChange={setUsername}
      />
    </>
  )
}

function readError(error: unknown) {
  if (error instanceof ApiError) {
    // 1) 422 字段级错误：把 details 翻译拼成"field: msg"列表
    if (error.status === 422 && Array.isArray(error.details) && error.details.length > 0) {
      const fieldMessages = error.details
        .map((d) => {
          if (!d || typeof d !== 'object') return null
          const entry = d as Record<string, unknown>
          const field = typeof entry.field === 'string' ? entry.field : ''
          const type = typeof entry.type === 'string' ? entry.type : ''
          const rawMsg = typeof entry.message === 'string' ? entry.message : ''
          if (!rawMsg) return null
          // 尝试用 type 在 errors 词条中找更友好的翻译
          const friendly = i18n.t(`errors:field_${type}`, { defaultValue: '' })
          const msgText = friendly || i18n.t(`errors:${error.code}`, { defaultValue: '' }) || rawMsg
          return field ? `${field}: ${msgText}` : msgText
        })
        .filter((s): s is string => Boolean(s))
      if (fieldMessages.length > 0) {
        return fieldMessages.join('; ')
      }
    }

    // 2) 用 i18n_key 翻
    if (error.i18nKey) {
      const translated = i18n.t(`errors:${error.i18nKey}`, { defaultValue: '' })
      if (translated) return translated
    }

    // 3) fallback：后端 message + trace_id
    if (error.message) return error.message
  }
  if (error instanceof Error) return error.message
  if (error && typeof error === 'object' && 'code' in error) {
    const code = String((error as { code?: string }).code ?? '')
    if (code) {
      const translated = i18n.t(`errors:${code}`, { defaultValue: '' })
      if (translated) return translated
      return code
    }
  }
  return i18n.t('common:request_failed')
}

function readStoredReturnPath(): string {
  try {
    return sessionStorage.getItem(RETURN_PATH_STORAGE_KEY) || ''
  } catch {
    return ''
  }
}

function clearStoredReturnPath(): void {
  try {
    sessionStorage.removeItem(RETURN_PATH_STORAGE_KEY)
  } catch {
    /* 忽略 */
  }
}
