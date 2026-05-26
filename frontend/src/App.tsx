import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  activateInterview,
  deleteResume,
  extractResume,
  finishInterview,
  getMe,
  getResume,
  getSession,
  listResumes,
  listSessions,
  login,
  register,
  replyInterviewStream,
  startInterviewStream,
} from './api'
import './App.css'
import {
  DEFAULT_DIFFICULTY_LEVEL,
  DEFAULT_HIGHLIGHTS,
  DEFAULT_JOB_TITLE,
  DEFAULT_LANGUAGE,
  DEFAULT_NOTICE,
  INTERVIEW_ROLE_OPTIONS,
  SESSION_STATUS_LABELS,
} from './constants'
import { EvaluationView } from './components/EvaluationView'
import { InterviewSessionView } from './components/InterviewSessionView'
import { PreparingStage } from './components/PreparingStage'
import { ConfirmDialog } from './components/ConfirmDialog'
import { ResumePreviewPanel } from './components/ResumePreviewPanel'
import type {
  AuthResponse,
  ChatMessage,
  InterviewQuestionPreview,
  InterviewSessionDetail,
  ResumeExtractResponse,
  ResumeSummary,
  SessionStatus,
  SessionSummary,
  StreamEvent,
  UserProfile,
} from './types'

type WorkspaceView = 'resume-manager' | 'composer' | 'preparing' | 'session' | 'evaluation'

type ResumeCardItem = ResumeSummary & {
  parse_status: 'processing' | 'ready'
}

const LOCAL_THINKING_MESSAGE_ID = 'local-thinking-message'

function App() {
  const [token, setToken] = useState<string>(() => localStorage.getItem('offer-agent-token') ?? '')
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [user, setUser] = useState<UserProfile | null>(null)
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [selectedSessionId, setSelectedSessionId] = useState<string>(() => localStorage.getItem('offer-agent-session') ?? '')
  const [currentSession, setCurrentSession] = useState<InterviewSessionDetail | null>(null)
  const [activeView, setActiveView] = useState<WorkspaceView>('resume-manager')
  const [resumes, setResumes] = useState<ResumeCardItem[]>([])
  const [isResumePreviewOpen, setIsResumePreviewOpen] = useState(false)
  const [selectedResumeId, setSelectedResumeId] = useState('')
  const [language, setLanguage] = useState(DEFAULT_LANGUAGE)
  const [difficultyLevel, setDifficultyLevel] = useState(DEFAULT_DIFFICULTY_LEVEL)
  const [jobTitle, setJobTitle] = useState(DEFAULT_JOB_TITLE)
  const [resumeText, setResumeText] = useState('')
  const [personalInfo, setPersonalInfo] = useState('')
  const [highlights, setHighlights] = useState(DEFAULT_HIGHLIGHTS)
  const [technicalSkills, setTechnicalSkills] = useState<string[]>([])
  const [workExperience, setWorkExperience] = useState<{ name: string; detail: string }[]>([])
  const [projectExperience, setProjectExperience] = useState<{ name: string; detail: string }[]>([])
  const [resumeFileName, setResumeFileName] = useState('')
  const [draftAnswer, setDraftAnswer] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [isExtracting, setIsExtracting] = useState(false)
  const [isPreparingInterview, setIsPreparingInterview] = useState(false)
  const [isActivatingInterview, setIsActivatingInterview] = useState(false)
  const [isFinishingInterview, setIsFinishingInterview] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState(DEFAULT_NOTICE)
  const [resumeDeleteTarget, setResumeDeleteTarget] = useState<{ resumeId: string; filename: string } | null>(null)
  const [isDeletingResume, setIsDeletingResume] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement | null>(null)

  const hasActiveSession = Boolean(currentSession && currentSession.status === 'active')
  const hasResumes = resumes.length > 0
  const selectedResumeSummary = useMemo(
    () => resumes.find((item) => item.id === selectedResumeId) ?? null,
    [resumes, selectedResumeId],
  )
  const selectedResumeReady = selectedResumeSummary?.parse_status === 'ready'
  const preparedOpeningMessage = useMemo(
    () => currentSession?.messages.find((item) => item.role === 'assistant') ?? null,
    [currentSession],
  )
  const answeredCount = useMemo(
    () => currentSession?.messages.filter((item) => item.role === 'user' && item.kind === 'answer').length ?? 0,
    [currentSession],
  )
  const isSessionWorkspace = activeView === 'session' || activeView === 'evaluation'
  const hasPreparedInterviewPreview = useMemo(() => {
    if (!currentSession || currentSession.status !== 'preparing') return false
    const hasOpeningQuestion = currentSession.messages.some((item) => item.role === 'assistant' && item.kind === 'question')
    return answeredCount === 0 && hasOpeningQuestion
  }, [answeredCount, currentSession])
  const totalQuestionCount = useMemo(() => getPlannedQuestionsFromSession(currentSession).length || 4, [currentSession])
  const completedQuestionCount = useMemo(() => {
    if (!currentSession) return 0
    const askedQuestionCount = currentSession.messages.filter(
      (item) => item.role === 'assistant' && item.kind === 'question',
    ).length
    if (currentSession.status === 'completed') {
      return totalQuestionCount
    }
    return Math.max(0, Math.min(totalQuestionCount, askedQuestionCount - 1))
  }, [currentSession, totalQuestionCount])
  const progressPercent = totalQuestionCount > 0 ? Math.round((completedQuestionCount / totalQuestionCount) * 100) : 0
  const plannedQuestions = useMemo(() => getPlannedQuestionsFromSession(currentSession), [currentSession])
  const sessionStatusLabel = (status: SessionStatus) => SESSION_STATUS_LABELS[status]

  useEffect(() => {
    localStorage.setItem('offer-agent-token', token)
  }, [token])

  useEffect(() => {
    localStorage.setItem('offer-agent-session', selectedSessionId)
  }, [selectedSessionId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [activeView, currentSession?.messages])

  const sessionTitle = useMemo(() => {
    if (activeView === 'resume-manager') return '我的简历'
    if (activeView === 'composer') return '新建教学版面试'
    if (activeView === 'preparing') return isPreparingInterview ? '正在生成题目' : '题目准备完成'
    if (activeView === 'evaluation') return '面试结果评估'
    return currentSession?.title ?? '选择一个会话'
  }, [activeView, currentSession, isPreparingInterview])

  const handleFatal = useCallback((err: unknown) => {
    setError(getErrorMessage(err))
    setToken('')
    setUser(null)
    localStorage.removeItem('offer-agent-token')
  }, [])

  const loadSession = useCallback(
    async (sessionId: string) => {
      try {
        const detail = await getSession(token, sessionId)
        setCurrentSession(detail)
        replaceSessionSummary(detail)
      } catch (err) {
        setError(getErrorMessage(err))
      }
    },
    [token],
  )

  const bootstrapAuthState = useCallback(async () => {
    try {
      const [profile, sessionList] = await Promise.all([getMe(token), listSessions(token)])
      const resumeList = await listResumes(token)
      setUser(profile)
      setSessions(sessionList)
      const resumeCards = resumeList.map((item) => ({ ...item, parse_status: 'ready' as const }))
      setResumes(resumeCards)
      setCurrentSession(null)
      setSelectedSessionId('')
      setSelectedResumeId((prev) => findReadyResume(resumeCards, prev)?.id ?? '')
      setActiveView('resume-manager')
    } catch (err) {
      handleFatal(err)
    }
  }, [handleFatal, token])

  useEffect(() => {
    if (!token) return
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void bootstrapAuthState()
  }, [bootstrapAuthState, token])

  useEffect(() => {
    if (!selectedResumeId) {
      return
    }
    const selected = resumes.find((item) => item.id === selectedResumeId)
    if (selected?.parse_status === 'ready') {
      return
    }
    setSelectedResumeId(findReadyResume(resumes)?.id ?? '')
  }, [resumes, selectedResumeId])

  useEffect(() => {
    if (!token || !selectedSessionId || !isSessionWorkspace) return
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadSession(selectedSessionId)
  }, [isSessionWorkspace, loadSession, selectedSessionId, token])

  function replaceSessionSummary(summary: SessionSummary) {
    setSessions((prev) => {
      const exists = prev.some((item) => item.id === summary.id)
      const next = exists ? prev.map((item) => (item.id === summary.id ? summary : item)) : [summary, ...prev]
      return [...next].sort((a, b) => b.updated_at.localeCompare(a.updated_at))
    })
  }

  function replaceResumeSummary(summary: ResumeSummary) {
    setResumes((prev) => {
      const exists = prev.some((item) => item.id === summary.id)
      const nextItem: ResumeCardItem = { ...summary, parse_status: 'ready' }
      const next = exists ? prev.map((item) => (item.id === summary.id ? nextItem : item)) : [nextItem, ...prev]
      return [...next].sort((a, b) => b.updated_at.localeCompare(a.updated_at))
    })
  }

  function upsertMessage(message: ChatMessage) {
    setCurrentSession((prev) => {
      if (!prev) return prev
      const exists = prev.messages.some((item) => item.id === message.id)
      const messages = exists
        ? prev.messages.map((item) => (item.id === message.id ? message : item))
        : [...prev.messages, message].sort((a, b) => a.seq - b.seq)
      return { ...prev, messages }
    })
  }

  function removeLocalThinkingMessage() {
    setCurrentSession((prev) =>
      prev
        ? {
            ...prev,
            messages: prev.messages.filter((item) => item.id !== LOCAL_THINKING_MESSAGE_ID),
          }
        : prev,
    )
  }

  function appendOptimisticUserMessage(content: string, seqOverride?: number) {
    if (!currentSession) return
    const nextSeq = seqOverride ?? (currentSession.messages.at(-1)?.seq ?? 0) + 1
    upsertMessage({
      id: `temp-${Date.now()}`,
      session_id: currentSession.id,
      seq: nextSeq,
      role: 'user',
      kind: 'answer',
      content,
      created_at: new Date().toISOString(),
      meta: {},
    })
  }

  function appendLocalThinkingMessage(seqOverride?: number) {
    if (!currentSession) return
    const nextSeq = seqOverride ?? (currentSession.messages.at(-1)?.seq ?? 0) + 1
    upsertMessage({
      id: LOCAL_THINKING_MESSAGE_ID,
      session_id: currentSession.id,
      seq: nextSeq,
      role: 'assistant',
      kind: 'thinking',
      content: '',
      created_at: new Date().toISOString(),
      meta: {},
    })
  }

  function applyResumeSnapshot(result: ResumeExtractResponse | ResumeSummary) {
    if (result.id) {
      setSelectedResumeId(result.id)
    }
    setResumeFileName(result.filename)
    setResumeText(result.resume_text)
    setPersonalInfo(result.personal_info)
    setHighlights(result.highlights.join(', '))
    setTechnicalSkills(result.technical_skills)
    setWorkExperience(result.work_experience)
    setProjectExperience(result.project_experience)
  }

  function applyExtractedResume(result: ResumeExtractResponse) {
    if (result.id) {
      const resumeId = result.id
      setSelectedResumeId(resumeId)
      setResumes((prev) => {
        const nextItem: ResumeCardItem = {
          id: resumeId,
          filename: result.filename,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          personal_info: result.personal_info,
          highlights: result.highlights,
          technical_skills: result.technical_skills,
          resume_text: result.resume_text,
          work_experience: result.work_experience,
          project_experience: result.project_experience,
          model_provider: result.model_provider,
          model_name: result.model_name,
          parse_status: 'ready',
        }
        const next = [nextItem, ...prev.filter((item) => item.id !== resumeId)]
        return next.sort((a, b) => b.updated_at.localeCompare(a.updated_at))
      })
    }
    applyResumeSnapshot(result)
  }

  function getFallbackProfile(targetRole = ''): InterviewSessionDetail['profile'] {
    return { job_title: '', target_role: targetRole, resume_text: '', highlights: [] }
  }

  function getPlannedQuestionsFromSession(session: Partial<InterviewSessionDetail> | null | undefined): InterviewQuestionPreview[] {
    return Array.isArray(session?.planned_questions) ? session.planned_questions : []
  }

  function handleStreamEvent(event: StreamEvent, localProfile?: InterviewSessionDetail['profile']) {
    if (event.event === 'session') {
      const summary = event.data.session as SessionSummary
      const plannedQuestions = (event.data.planned_questions as InterviewQuestionPreview[] | undefined) ?? []
      setSelectedSessionId(summary.id)
      replaceSessionSummary(summary)
      setCurrentSession({
        ...summary,
        profile: localProfile ?? currentSession?.profile ?? getFallbackProfile(summary.target_role),
        planned_questions: plannedQuestions,
        messages: [],
        evaluation: null,
      })
      setActiveView('preparing')
      setUser((prev) =>
        prev
          ? {
              ...prev,
              quota_remaining:
                typeof event.data.quota_remaining === 'number' ? event.data.quota_remaining : prev.quota_remaining,
            }
          : prev,
      )
      return
    }

    if (event.event === 'message_start') {
      const message = event.data.message as ChatMessage
      removeLocalThinkingMessage()
      upsertMessage({ ...message, content: '' })
      return
    }

    if (event.event === 'delta') {
      const messageId = event.data.message_id as string
      setCurrentSession((prev) => {
        if (!prev) return prev
        return {
          ...prev,
          messages: prev.messages.map((item) =>
            item.id === messageId ? { ...item, content: `${item.content}${event.data.delta as string}` } : item,
          ),
        }
      })
      return
    }

    if (event.event === 'message_end') {
      removeLocalThinkingMessage()
      upsertMessage(event.data.message as ChatMessage)
      return
    }

    if (event.event === 'evaluation') {
      setCurrentSession((prev) =>
        prev ? { ...prev, evaluation: event.data.evaluation as InterviewSessionDetail['evaluation'] } : prev,
      )
      return
    }

    if (event.event === 'done') {
      const sessionId = event.data.session_id as string
      setIsPreparingInterview(false)
      setIsStreaming(false)
      void loadSession(sessionId)
    }
  }

  async function handleAuthSubmit() {
    setError('')
    setIsLoading(true)
    try {
      const response: AuthResponse =
        authMode === 'login' ? await login(username.trim(), password) : await register(username.trim(), password)
      setToken(response.access_token)
      setUser(response.user)
      setPassword('')
      setNotice(authMode === 'login' ? '登录成功' : '注册成功，已自动登录')
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setIsLoading(false)
    }
  }

  async function handleResumeUpload(file: File | null) {
    if (!file) return
    const tempId = `temp-${Date.now()}`
    setError('')
    setIsExtracting(true)
    setIsResumePreviewOpen(false)
    setResumes((prev) => [
      {
        id: tempId,
        filename: file.name,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        personal_info: '',
        highlights: [],
        technical_skills: [],
        resume_text: '',
        work_experience: [],
        project_experience: [],
        model_provider: '',
        model_name: '',
        parse_status: 'processing',
      },
      ...prev.filter((item) => item.id !== tempId),
    ])
    try {
      const result = await extractResume(token, file)
      setResumes((prev) => prev.filter((item) => item.id !== tempId))
      applyExtractedResume(result)
      setIsResumePreviewOpen(true)
      setNotice(`已解析简历：${result.filename}，现在可以查看解析结果或发起模拟面试`)
    } catch (err) {
      setResumes((prev) => prev.filter((item) => item.id !== tempId))
      setError(getErrorMessage(err))
    } finally {
      setIsExtracting(false)
    }
  }

  function clearResumeSnapshot() {
    setSelectedResumeId('')
    setResumeFileName('')
    setResumeText('')
    setPersonalInfo('')
    setHighlights(DEFAULT_HIGHLIGHTS)
    setTechnicalSkills([])
    setWorkExperience([])
    setProjectExperience([])
    setIsResumePreviewOpen(false)
  }

  function requestResumeDelete(resumeId: string, filename: string) {
    setResumeDeleteTarget({ resumeId, filename })
  }

  async function confirmResumeDelete() {
    if (!resumeDeleteTarget) {
      return
    }

    const { resumeId, filename } = resumeDeleteTarget
    const target = resumes.find((item) => item.id === resumeId)
    if (target?.parse_status === 'processing' && resumeId.startsWith('temp-')) {
      setResumes((prev) => prev.filter((item) => item.id !== resumeId))
      if (selectedResumeId === resumeId) {
        clearResumeSnapshot()
      }
      setResumeDeleteTarget(null)
      setNotice('已取消上传')
      return
    }

    setError('')
    setIsDeletingResume(true)
    try {
      await deleteResume(token, resumeId)
      const remaining = resumes.filter((item) => item.id !== resumeId)
      setResumes(remaining)
      if (selectedResumeId === resumeId) {
        const nextReady = remaining.find((item) => item.parse_status === 'ready')
        if (nextReady) {
          await handleResumeSelect(nextReady.id)
        } else {
          clearResumeSnapshot()
        }
      }
      setResumeDeleteTarget(null)
      setNotice(`已删除简历：${filename}`)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setIsDeletingResume(false)
    }
  }

  async function handleResumeSelect(resumeId: string) {
    setSelectedResumeId(resumeId)
    const selected = resumes.find((item) => item.id === resumeId)
    if (!resumeId) {
      return
    }
    if (selected?.parse_status === 'processing') {
      setNotice('这份简历还在解析中，解析完成后才能用于面试')
      return
    }
    setError('')
    try {
      const result = await getResume(token, resumeId)
      replaceResumeSummary(result)
      applyResumeSnapshot(result)
      setNotice(`已载入简历：${result.filename}`)
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  async function handleStartInterview() {
    if (!selectedResumeId || !selectedResumeReady) {
      setError('请先选择一份解析完成的简历，再开始模拟面试')
      setActiveView('resume-manager')
      return
    }
    if (!resumeText.trim()) {
      setError('请先上传并解析简历，或重新选择一份已有简历')
      return
    }
    setError('')
    setIsStreaming(true)
    setIsPreparingInterview(true)
    setSelectedSessionId('')
    setCurrentSession(null)
    setActiveView('preparing')
    const profile = {
      resume_id: selectedResumeId,
      job_title: jobTitle.trim(),
      target_role: jobTitle.trim(),
      language,
      difficulty_level: difficultyLevel,
      resume_text: resumeText.trim(),
      personal_info: personalInfo.trim(),
      highlights: highlights
        .split(/[,\n]/)
        .map((item) => item.trim())
        .filter(Boolean),
      technical_skills: technicalSkills,
      work_experience: workExperience,
      project_experience: projectExperience,
      resume_filename: resumeFileName,
    }

    try {
      await startInterviewStream(token, profile, (event) => handleStreamEvent(event, profile))
      setNotice('题目已准备完成，可以先查看首题，再正式开始面试')
    } catch (err) {
      setError(getErrorMessage(err))
      setIsPreparingInterview(false)
      setActiveView('composer')
    } finally {
      setIsStreaming(false)
    }
  }

  async function handleReply() {
    if (!currentSession || !draftAnswer.trim()) {
      return
    }
    const content = draftAnswer.trim()
    const baseSeq = currentSession.messages.at(-1)?.seq ?? 0
    setDraftAnswer('')
    setError('')
    setIsStreaming(true)
    appendOptimisticUserMessage(content, baseSeq + 1)
    appendLocalThinkingMessage(baseSeq + 2)

    try {
      await replyInterviewStream(token, currentSession.id, content, handleStreamEvent)
    } catch (err) {
      removeLocalThinkingMessage()
      setError(getErrorMessage(err))
      setIsStreaming(false)
    }
  }

  function handleLogout() {
    setToken('')
    setUser(null)
    setSessions([])
    setCurrentSession(null)
    setSelectedSessionId('')
    setResumes([])
    setSelectedResumeId('')
    setIsPreparingInterview(false)
    setIsFinishingInterview(false)
    setIsResumePreviewOpen(false)
    setActiveView('resume-manager')
    setNotice('已退出登录')
  }

  function openSessionWorkspace(sessionId: string, view: Extract<WorkspaceView, 'session' | 'evaluation'>) {
    setIsPreparingInterview(false)
    setIsFinishingInterview(false)
    setActiveView(view)
    setSelectedSessionId(sessionId)
  }

  function selectSession(session: SessionSummary) {
    setCurrentSession({
      ...session,
      profile: getFallbackProfile(session.target_role),
      planned_questions: [],
      messages: [],
      evaluation: null,
    })
    if (session.status === 'completed') {
      openSessionWorkspace(session.id, 'evaluation')
      return
    }
    if (session.status === 'preparing') {
      setIsPreparingInterview(false)
      setActiveView('preparing')
      setSelectedSessionId(session.id)
      void loadSession(session.id)
      return
    }
    openSessionWorkspace(session.id, 'session')
  }

  function openComposer() {
    if (!hasResumes) {
      setActiveView('resume-manager')
      setCurrentSession(null)
      setSelectedSessionId('')
      setIsPreparingInterview(false)
      setIsResumePreviewOpen(false)
      setNotice('请先上传并解析简历，之后再开始模拟面试')
      return
    }
    setActiveView('composer')
    setCurrentSession(null)
    setSelectedSessionId('')
    setIsPreparingInterview(false)
    setIsFinishingInterview(false)
    setIsResumePreviewOpen(false)
    const nextResume = findReadyResume(resumes, selectedResumeId)
    setSelectedResumeId(nextResume?.id ?? '')
    setLanguage(DEFAULT_LANGUAGE)
    setDifficultyLevel(DEFAULT_DIFFICULTY_LEVEL)
    setJobTitle(DEFAULT_JOB_TITLE)
    if (nextResume) {
      applyResumeSnapshot(nextResume)
    } else {
      setResumeText('')
      setPersonalInfo('')
      setHighlights(DEFAULT_HIGHLIGHTS)
      setTechnicalSkills([])
      setWorkExperience([])
      setProjectExperience([])
      setResumeFileName('')
    }
  }

  function openResumeManager() {
    setActiveView('resume-manager')
    setIsPreparingInterview(false)
    setIsFinishingInterview(false)
    setError('')
  }

  function openInterviewHome() {
    if (!hasResumes) {
      setActiveView('resume-manager')
      setNotice('请先上传并解析简历，之后才能进入模拟面试')
      return
    }
    if (hasPreparedInterviewPreview && currentSession) {
      setSelectedSessionId(currentSession.id)
      setActiveView('preparing')
      setIsResumePreviewOpen(false)
      return
    }
    openComposer()
  }

  async function openPreparedInterview() {
    if (!currentSession) return
    setError('')
    setIsActivatingInterview(true)
    try {
      const detail = await activateInterview(token, currentSession.id)
      setCurrentSession(detail)
      replaceSessionSummary(detail)
      setSelectedSessionId(detail.id)
      setActiveView('session')
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setIsActivatingInterview(false)
    }
  }

  function openResumePreview(resumeId: string) {
    if (isResumePreviewOpen && selectedResumeId === resumeId) {
      setIsResumePreviewOpen(false)
      return
    }
    setIsResumePreviewOpen(true)
    void handleResumeSelect(resumeId)
  }

  function handleFinishInterview() {
    if (!currentSession) return
    setError('')
    setIsStreaming(true)
    setIsFinishingInterview(true)
    setActiveView('evaluation')
    setNotice('正在生成正式评估，请稍等。')
    void finishInterview(token, currentSession.id)
      .then((detail) => {
        setCurrentSession(detail)
        replaceSessionSummary(detail)
        setSelectedSessionId(detail.id)
        setNotice('正式评估已生成完成。')
      })
      .catch((err) => {
        setActiveView('session')
        setError(getErrorMessage(err))
      })
      .finally(() => {
        setIsStreaming(false)
        setIsFinishingInterview(false)
      })
  }

  return (
    <div className="app-shell">
      {!token ? (
        <section className="auth-shell">
          <div className="auth-card">
            <p className="eyebrow">Offer Agent</p>
            <h1>教学版 CV 面试工作台</h1>
            <p className="auth-copy">前后端分离、JWT 登录、额度计数、SSE 流式交互，以及可恢复的面试会话。</p>
            <div className="segmented">
              <button className={authMode === 'login' ? 'active' : ''} onClick={() => setAuthMode('login')}>
                登录
              </button>
              <button className={authMode === 'register' ? 'active' : ''} onClick={() => setAuthMode('register')}>
                注册
              </button>
            </div>
            <label>
              用户名
              <input value={username} onChange={(event) => setUsername(event.target.value)} placeholder="demo_user" />
            </label>
            <label>
              密码
              <input
                value={password}
                type="password"
                onChange={(event) => setPassword(event.target.value)}
                placeholder="至少 6 位"
              />
            </label>
            <button className="primary" disabled={isLoading} onClick={handleAuthSubmit}>
              {isLoading ? '提交中...' : authMode === 'login' ? '登录' : '注册并登录'}
            </button>
            {error ? <p className="error-text">{error}</p> : <p className="notice-text">{notice}</p>}
          </div>
        </section>
      ) : (
        <div className="workspace">
          <aside className="sidebar">
            <div className="user-card">
              <div className="sidebar-header">
                <div className="sidebar-user">
                  <div className="user-avatar" aria-hidden="true">
                    {getAvatarText(user?.username)}
                  </div>
                  <div className="user-copy">
                    <p className="eyebrow">Offer Agent</p>
                    <h2>{user?.username}</h2>
                    <p className="user-subtitle">模拟面试助手</p>
                  </div>
                </div>
                <button className="ghost ghost-compact sidebar-logout" onClick={handleLogout}>
                  退出
                </button>
              </div>
              <div className="quota-card">
                <span>剩余额度</span>
                <strong>{user?.quota_remaining ?? 0}</strong>
                <small>每次新建面试会消耗 1 次额度</small>
              </div>
            </div>
            <div className="sidebar-actions">
              <button
                className={`sidebar-action ${activeView === 'resume-manager' ? 'active' : ''}`}
                onClick={openResumeManager}
              >
                简历管理
              </button>
              <button
                className={`sidebar-action ${activeView === 'composer' || activeView === 'preparing' ? 'active' : ''}`}
                onClick={openInterviewHome}
                disabled={!hasResumes}
              >
                新建面试
              </button>
            </div>
            {!hasResumes ? <div className="sidebar-empty">请先进入“简历管理”上传并解析简历，之后再创建模拟面试。</div> : null}
            <p className="sidebar-section-title">面试会话信息</p>
            <div className="session-list">
              {sessions.length > 0 ? (
                sessions.map((session) => (
                  <button
                    key={session.id}
                    className={`session-item ${isSessionWorkspace && session.id === selectedSessionId ? 'active' : ''}`}
                    onClick={() => selectSession(session)}
                  >
                    <span>{session.title}</span>
                    <small>{sessionStatusLabel(session.status)}</small>
                    <time className="session-time">{formatSessionTime(session.created_at)}</time>
                  </button>
                ))
              ) : (
                <div className="sidebar-empty">还没有面试记录，先上传简历，再点击“新建面试”。</div>
              )}
            </div>
          </aside>

          <main className="chat-layout">
            {activeView !== 'session' ? (
              <header className="chat-header">
                <div className="chat-header-main">
                  <p className="eyebrow">脱敏教学版</p>
                  <h1>{sessionTitle}</h1>
                  <p className="chat-subtitle">
                    {activeView === 'resume-manager'
                      ? '先管理并解析简历，再从左侧点击“新建面试”进入模拟面试。'
                      : activeView === 'composer'
                        ? '围绕已上传简历设置语言、岗位与难度，先生成题目，再正式开始模拟面试。'
                        : activeView === 'preparing'
                          ? '系统会先生成题目和开场问题，确认后再正式进入面试对话。'
                          : '评分、总结、优势与改进建议已单独放到结果评估页面。'}
                  </p>
                </div>
                <p className="notice-text">{notice}</p>
              </header>
            ) : null}

            {activeView === 'resume-manager' ? (
              <section className="resume-page">
                <div className="resume-page-header">
                  <h3>我的简历({resumes.length}/3)</h3>
                </div>
                <div className="resume-grid">
                  {resumes.map((resume) => (
                    <div
                      key={resume.id}
                      className={`resume-card ${resume.id === selectedResumeId ? 'active' : ''} ${resume.parse_status === 'processing' ? 'processing' : ''}`}
                    >
                      <button
                        type="button"
                        className="resume-card-delete"
                        aria-label={`删除 ${resume.filename}`}
                        onClick={() => requestResumeDelete(resume.id, resume.filename)}
                      >
                        <TrashIcon />
                      </button>
                      <div className="resume-card-icon">
                        <span className="resume-badge">{getResumeBadge(resume.filename)}</span>
                      </div>
                      <button
                        className="resume-card-main"
                        type="button"
                        disabled={resume.parse_status !== 'ready'}
                        onClick={() => void handleResumeSelect(resume.id)}
                      >
                        <strong>{resume.filename}</strong>
                        <p>{formatResumeMeta(resume)}</p>
                        <div className="resume-status">
                          {resume.parse_status === 'processing' ? <span className="resume-spinner" aria-hidden="true" /> : null}
                          <span>{resume.parse_status === 'processing' ? '解析中' : '已解析完成'}</span>
                        </div>
                      </button>
                      <div className="resume-card-actions">
                        <button
                          className="ghost ghost-compact"
                          type="button"
                          disabled={resume.parse_status !== 'ready'}
                          onClick={() => openResumePreview(resume.id)}
                        >
                          查看结果
                        </button>
                      </div>
                    </div>
                  ))}
                  <label className="resume-upload-card">
                    <input
                      type="file"
                      accept=".pdf,.txt,.md,.docx"
                      onChange={(event) => void handleResumeUpload(event.target.files?.[0] ?? null)}
                    />
                    <span className="resume-upload-plus">+</span>
                    <strong>{isExtracting ? '简历解析中...' : '点击添加简历'}</strong>
                    <p>支持 pdf、doc、docx、txt、md 格式</p>
                  </label>
                </div>
                {selectedResumeSummary ? (
                  <div className="resume-page-tip">
                    当前选中：{selectedResumeSummary.filename}。
                    {selectedResumeSummary.parse_status === 'ready'
                      ? ' 这份简历已可用于模拟面试。'
                      : ' 这份简历仍在解析中，暂时不能用于面试。'}
                  </div>
                ) : (
                  <div className="resume-page-tip">请先上传一份简历，完成解析后再去新建面试。</div>
                )}
                {isResumePreviewOpen && selectedResumeSummary?.parse_status === 'ready' ? (
                  <ResumePreviewPanel
                    resume={selectedResumeSummary}
                    updatedAtText={formatSessionTime(selectedResumeSummary.updated_at).replace('面试时间 ', '')}
                  />
                ) : null}
                {error ? <p className="error-text">{error}</p> : null}
              </section>
            ) : activeView === 'composer' ? (
              <section className="composer-sheet">
                <div className="form-card">
                  <h3>开始新的模拟面试</h3>
                  <p className="form-helper">先选择已上传简历，再设置语言、岗位与难度。只有解析完成的简历才能生成题目。</p>
                  <label className="required">
                    选择我的简历
                    <select
                      value={selectedResumeReady ? selectedResumeId : ''}
                      onChange={(event) => {
                        if (!event.target.value) {
                          setSelectedResumeId('')
                          clearResumeSnapshot()
                          return
                        }
                        void handleResumeSelect(event.target.value)
                      }}
                    >
                      <option value="">请选择</option>
                      {resumes.map((resume) => (
                        <option key={resume.id} value={resume.id} disabled={resume.parse_status !== 'ready'}>
                          {resume.filename}{resume.parse_status === 'processing' ? '（解析中）' : ''}
                        </option>
                      ))}
                    </select>
                  </label>
                  {resumeFileName ? (
                    <p className="form-tips">
                      当前简历：{resumeFileName}
                      {selectedResumeReady ? '，已完成解析，可用于生成题目。' : '，仍在解析中，暂不可用于面试。'}
                    </p>
                  ) : (
                    <p className="form-tips">请先从左侧“简历管理”页上传或选择一份简历。</p>
                  )}
                  <label className="required">
                    语言
                    <select value={language} onChange={(event) => setLanguage(event.target.value)}>
                      <option value="Java">Java</option>
                      <option value="Python">Python</option>
                      <option value="Go">Go</option>
                      <option value="JavaScript">JavaScript</option>
                    </select>
                  </label>
                  <label className="required">
                    岗位名称
                    <select value={jobTitle} onChange={(event) => setJobTitle(event.target.value)}>
                      {INTERVIEW_ROLE_OPTIONS.map((role) => (
                        <option key={role} value={role}>
                          {role}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    难度等级
                    <select value={difficultyLevel} onChange={(event) => setDifficultyLevel(event.target.value)}>
                      <option value="入门">入门</option>
                      <option value="进阶">进阶</option>
                      <option value="挑战">挑战</option>
                    </select>
                  </label>
                  <button className="start-button" disabled={isStreaming || isExtracting || !selectedResumeReady} onClick={handleStartInterview}>
                    {isExtracting ? '解析中...' : isPreparingInterview ? '出题中...' : isStreaming ? '生成中...' : '生成题目'}
                  </button>
                  <p className="remaining-text">剩余 {user?.quota_remaining ?? 0} 次</p>
                  {error ? <p className="error-text">{error}</p> : null}
                </div>
              </section>
            ) : activeView === 'preparing' ? (
              <PreparingStage
                title={currentSession?.title ?? '模拟面试'}
                openingMessage={preparedOpeningMessage?.content || ''}
                questions={plannedQuestions}
                isPreparing={isPreparingInterview}
                isActivating={isActivatingInterview}
                canStart={!isPreparingInterview && !isActivatingInterview && Boolean(currentSession)}
                onBack={openComposer}
                onStart={() => void openPreparedInterview()}
              />
            ) : activeView === 'session' ? (
              <InterviewSessionView
                title={currentSession?.title ?? '综合面试'}
                messages={currentSession?.messages ?? []}
                draftAnswer={draftAnswer}
                answeredCount={answeredCount}
                totalQuestionCount={totalQuestionCount}
                completedQuestionCount={completedQuestionCount}
                progressPercent={progressPercent}
                hasActiveSession={hasActiveSession}
                isStreaming={isStreaming}
                hasEvaluation={Boolean(currentSession?.evaluation)}
                currentUserAvatar={getAvatarText(user?.username)}
                messagesEndRef={messagesEndRef}
                onDraftAnswerChange={setDraftAnswer}
                onReply={() => void handleReply()}
                onFinish={handleFinishInterview}
                onOpenEvaluation={() => currentSession && openSessionWorkspace(currentSession.id, 'evaluation')}
                formatMessageTime={formatMessageTime}
              />
            ) : (
              <section className="evaluation-page">
                <EvaluationView
                  title={currentSession?.title ?? '面试结果评估'}
                  totalQuestionCount={totalQuestionCount}
                  evaluation={currentSession?.evaluation ?? null}
                  isLoading={isFinishingInterview}
                  onOpenSession={
                    currentSession ? () => openSessionWorkspace(currentSession.id, 'session') : undefined
                  }
                  onRestart={openComposer}
                />
              </section>
            )}
          </main>
        </div>
      )}
      <ConfirmDialog
        open={resumeDeleteTarget !== null}
        title="删除简历"
        description={
          resumeDeleteTarget
            ? `确定删除「${resumeDeleteTarget.filename}」吗？删除后无法恢复，进行中的面试记录仍会保留当时的简历快照。`
            : ''
        }
        confirmLabel="删除"
        cancelLabel="取消"
        danger
        loading={isDeletingResume}
        onCancel={() => {
          if (!isDeletingResume) {
            setResumeDeleteTarget(null)
          }
        }}
        onConfirm={() => void confirmResumeDelete()}
      />
    </div>
  )
}

export default App

function findReadyResume(resumes: ResumeCardItem[], preferredId?: string): ResumeCardItem | null {
  if (preferredId) {
    const preferred = resumes.find((item) => item.id === preferredId && item.parse_status === 'ready')
    if (preferred) {
      return preferred
    }
  }
  return resumes.find((item) => item.parse_status === 'ready') ?? null
}

function getErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : '发生未知错误'
}

function getAvatarText(username?: string | null) {
  const value = (username ?? '').trim()
  return value ? value.slice(0, 1).toUpperCase() : 'U'
}

function TrashIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M3.5 4.5h9M6 4.5V3.25A.75.75 0 0 1 6.75 2.5h2.5a.75.75 0 0 1 .75.75V4.5M6.25 7v4.25M9.75 7v4.25M4.25 4.5l.5 8.25A1 1 0 0 0 5.75 13.75h4.5a1 1 0 0 0 1-1l.5-8.25"
        stroke="currentColor"
        strokeWidth="1.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function getResumeBadge(filename: string) {
  const extension = filename.split('.').pop()?.toUpperCase() ?? 'FILE'
  return extension.length <= 4 ? extension : 'FILE'
}

function formatResumeMeta(resume: ResumeSummary) {
  const stamp = new Date(resume.updated_at || resume.created_at)
  const dateText = Number.isNaN(stamp.getTime())
    ? '已解析'
    : `${stamp.getFullYear()}-${String(stamp.getMonth() + 1).padStart(2, '0')}-${String(stamp.getDate()).padStart(2, '0')} ${String(stamp.getHours()).padStart(2, '0')}:${String(stamp.getMinutes()).padStart(2, '0')}:${String(stamp.getSeconds()).padStart(2, '0')}`
  const tags = resume.highlights.slice(0, 2).join(' | ')
  return tags ? `${tags} | ${dateText}` : dateText
}

function formatMessageTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '--:--:--'
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}:${String(date.getSeconds()).padStart(2, '0')}`
}

function formatSessionTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '面试时间 --'
  return `面试时间 ${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}
