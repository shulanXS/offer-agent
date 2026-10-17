/**
 * v3.7 路由与壳层
 *
 * R7 重要改动：
 * - 登录对话框状态 → useAuthDialog hook
 * - 简历 CRUD → useResumes hook
 * - 登录后跳转目标 → useReturnUrl hook
 * - client.ts fetch 默认 keepalive: true
 * - 401 处理收敛：只清 token，由 AppRoutes 自然落到登录页
 */
import { useEffect, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { AppSidebar } from './components/AppSidebar'
import { AuthDialog, AuthLoading } from './components/AuthPage'
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
import type { AuthResponse, UserProfile } from './types'
import { useRouteRemountKey } from './hooks/useRouteQueryRefetch'
import { useAuthDialog } from './hooks/useAuthDialog'
import { useResumes } from './hooks/useResumes'
import { useReturnUrl } from './hooks/useReturnUrl'
import { getStoredToken, registerUnauthorizedHandler, setStoredToken, ApiError } from './services/client'
import i18n from './i18n'
import './App.css'

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
  const returnUrl = useReturnUrl()
  const initialToken = getStoredToken()
  const [token, setToken] = useState(initialToken)
  const [user, setUser] = useState<UserProfile | null>(null)
  const [isLoading, setIsLoading] = useState(Boolean(initialToken))
  const [isBillingOpen, setIsBillingOpen] = useState(false)

  const authDialog = useAuthDialog()
  const resumes = useResumes(token)

  // 401 处理：仅清 token；UI 由 user/token 状态自然收敛到登录页。
  useEffect(() => {
    registerUnauthorizedHandler(() => {
      clearAuth({ skipNavigate: true })
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!token) {
      return
    }
    let active = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIsLoading(true)
    getMe(token)
      .then((profile) => {
        if (!active) return
        setUser(profile)
      })
      .catch((err: unknown) => {
        if (!active) return
        if (!(err instanceof ApiError) || err.status !== 401) {
          resumes.setError(readError(err))
        }
      })
      .finally(() => {
        if (active) setIsLoading(false)
      })
    return () => {
      active = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  function clearAuth(options: { skipNavigate?: boolean } = {}) {
    setStoredToken('')
    setToken('')
    setUser(null)
    authDialog.close()
    if (!options.skipNavigate) {
      navigate('/')
    }
  }

  async function handleAuthSubmit() {
    authDialog.setError('')
    authDialog.setNotice('')
    authDialog.setIsSubmitting(true)
    try {
      const response: AuthResponse =
        authDialog.mode === 'login'
          ? await login(authDialog.username.trim(), authDialog.password)
          : await register(authDialog.username.trim(), authDialog.password)
      setStoredToken(response.access_token)
      setToken(response.access_token)
      setUser(response.user)
      authDialog.reset()
      authDialog.setNotice(i18n.t(`auth:notice_${authDialog.mode}`))
      authDialog.close()

      const returnPath = returnUrl.read()
      if (returnPath) {
        returnUrl.clear()
        navigate(returnPath, { replace: true })
      } else {
        navigate('/resumes')
      }
    } catch (err) {
      authDialog.setError(readError(err))
    } finally {
      authDialog.setIsSubmitting(false)
    }
  }

  // 未登录态下，已登录专属 URL 一律跳回首页
  useEffect(() => {
    if (!token || !user) {
      if (location.pathname !== '/' && location.pathname !== '/billing/return') {
        navigate('/', { replace: true })
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, user?.id, location.pathname])

  if (isLoading && token && !user) {
    return <AuthLoading />
  }

  if (location.pathname === '/billing/return') {
    return <BillingReturnPage />
  }

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
                  error={resumes.error}
                  resumes={resumes.resumes}
                  selectedResume={resumes.selectedResume}
                  isExtracting={resumes.isExtracting}
                  deletingResumeId={resumes.deletingResumeId}
                  onResumeSelect={resumes.onSelect}
                  onResumeUpload={resumes.onUpload}
                  onResumeDelete={resumes.onDelete}
                />
              }
            />
            <Route
              path="/interviews/new"
              element={<InterviewConfigurationPage token={token} resumes={resumes.resumes} selectedResume={resumes.selectedResume} />}
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

  return (
    <>
      <PublicShell
        onLoginClick={() => authDialog.open('login')}
        onRegisterClick={() => authDialog.open('register')}
      >
        <PublicHome
          onLoginClick={() => authDialog.open('login')}
          onRegisterClick={() => authDialog.open('register')}
        />
      </PublicShell>
      <AuthDialog
        open={authDialog.isOpen}
        authMode={authDialog.mode}
        error={authDialog.error}
        isSubmitting={authDialog.isSubmitting}
        notice={authDialog.notice}
        password={authDialog.password}
        username={authDialog.username}
        onClose={authDialog.close}
        onAuthModeChange={authDialog.setMode}
        onPasswordChange={authDialog.setPassword}
        onSubmit={handleAuthSubmit}
        onUsernameChange={authDialog.setUsername}
      />
    </>
  )
}

function readError(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 422 && Array.isArray(error.details) && error.details.length > 0) {
      const fieldMessages = error.details
        .map((d) => {
          if (!d || typeof d !== 'object') return null
          const entry = d as Record<string, unknown>
          const field = typeof entry.field === 'string' ? entry.field : ''
          const type = typeof entry.type === 'string' ? entry.type : ''
          const rawMsg = typeof entry.message === 'string' ? entry.message : ''
          if (!rawMsg) return null
          const friendly = i18n.t(`errors:field_${type}`, { defaultValue: '' })
          const msgText = friendly || i18n.t(`errors:${error.code}`, { defaultValue: '' }) || rawMsg
          return field ? `${field}: ${msgText}` : msgText
        })
        .filter((s): s is string => Boolean(s))
      if (fieldMessages.length > 0) {
        return fieldMessages.join('; ')
      }
    }

    if (error.i18nKey) {
      const translated = i18n.t(`errors:${error.i18nKey}`, { defaultValue: '' })
      if (translated) return translated
    }

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
