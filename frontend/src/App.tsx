import { useEffect, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { AppSidebar } from './components/AppSidebar'
import { AuthLoading, AuthPage, type AuthMode } from './components/AuthPage'
import { InterviewConfigurationPage } from './pages/InterviewConfigurationPage'
import { InterviewEvaluationPage } from './pages/InterviewEvaluationPage'
import { InterviewLivePage } from './pages/InterviewLivePage'
import { InterviewPlanPage } from './pages/InterviewPlanPage'
import { InterviewRecordsPage } from './pages/InterviewRecordsPage'
import { ResumesPage } from './pages/ResumesPage'
import { getMe, login, register } from './services/auth'
import { deleteResume, extractResume, getResume, listResumes } from './services/resume'
import type { AuthResponse, ResumeSummary, UserProfile } from './types'
import { useRouteRemountKey } from './hooks/useRouteQueryRefetch'
import {
  createProcessingResume,
  MAX_RESUME_COUNT,
  replaceResume,
  toResumeCardItem,
  toResumeSummary,
  type ResumeCardItem,
} from './utils/resume'
import { getStoredToken, registerUnauthorizedHandler, setStoredToken } from './services/client'
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
  const [token, setToken] = useState(() => getStoredToken())
  const [authMode, setAuthMode] = useState<AuthMode>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [user, setUser] = useState<UserProfile | null>(null)
  const [resumes, setResumes] = useState<ResumeCardItem[]>([])
  const [selectedResume, setSelectedResume] = useState<ResumeSummary | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [isLoading, setIsLoading] = useState(Boolean(token))
  const [isSubmittingAuth, setIsSubmittingAuth] = useState(false)
  const [isExtracting, setIsExtracting] = useState(false)
  const [deletingResumeId, setDeletingResumeId] = useState('')

  // C4：401 自动清 token 并跳登录
  useEffect(() => {
    registerUnauthorizedHandler(() => {
      clearAuth()
      navigate('/')
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!token) {
      setIsLoading(false)
      return
    }

    let active = true
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
        clearAuth()
        setError(readError(err))
      })
      .finally(() => {
        if (active) setIsLoading(false)
      })

    return () => {
      active = false
    }
  }, [token])

  function clearAuth() {
    setStoredToken('')
    setToken('')
    setUser(null)
    setResumes([])
    setSelectedResume(null)
    setIsLoading(false)
  }

  async function handleAuthSubmit() {
    setError('')
    setNotice('')
    setIsSubmittingAuth(true)
    try {
      const response: AuthResponse =
        authMode === 'login' ? await login(username.trim(), password) : await register(username.trim(), password)
      setStoredToken(response.access_token)
      setToken(response.access_token)
      setUser(response.user)
      setPassword('')
      setNotice(authMode === 'login' ? '登录成功' : '注册成功，已自动登录')

      const returnPath = `${location.pathname}${location.search}`
      if (returnPath.startsWith('/interviews/')) {
        navigate(returnPath, { replace: true })
      }
    } catch (err) {
      setError(readError(err))
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
      setError(`最多保留 ${MAX_RESUME_COUNT} 份简历，请先删除不需要的简历。`)
      return
    }

    const processingResume = createProcessingResume(file.name)
    setError('')
    setIsExtracting(true)
    setResumes((prev) => [processingResume, ...prev])

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
  }

  if (isLoading && token && !user) {
    return <AuthLoading />
  }

  if (!user) {
    return (
      <AuthPage
        authMode={authMode}
        error={error}
        isSubmitting={isSubmittingAuth}
        notice={notice}
        password={password}
        username={username}
        onAuthModeChange={setAuthMode}
        onPasswordChange={setPassword}
        onSubmit={handleAuthSubmit}
        onUsernameChange={setUsername}
      />
    )
  }

  return (
    <main className="v2-shell">
      <AppSidebar user={user} onLogout={clearAuth} />
      <section className="v2-content" key={routeRemountKey}>
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
          <Route path="*" element={<Navigate to="/resumes" replace />} />
        </Routes>
      </section>
    </main>
  )
}

function readError(error: unknown) {
  return error instanceof Error ? error.message : '请求失败'
}
