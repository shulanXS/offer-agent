/**R7：简历列表 CRUD hook。**

封装 list / upload / select / delete / processing-id 同步等能力，把
原 App.tsx 里的 resume 状态机和持久化处理抽出来。
*/
import { useCallback, useEffect, useRef, useState } from 'react'
import { deleteResume, extractResume, getResume, listResumes } from '../services/resume'
import type { ResumeSummary } from '../types'
import {
  createProcessingResume,
  loadPersistedProcessingIds,
  MAX_RESUME_COUNT,
  persistProcessingIds,
  replaceResume,
  toResumeCardItem,
  toResumeSummary,
  type ResumeCardItem,
} from '../utils/resume'

export function useResumes(token: string | null) {
  const [resumes, setResumes] = useState<ResumeCardItem[]>([])
  const [selectedResume, setSelectedResume] = useState<ResumeSummary | null>(null)
  const [isExtracting, setIsExtracting] = useState(false)
  const [deletingResumeId, setDeletingResumeId] = useState('')
  const [error, setError] = useState('')
  const processingIdsRef = useRef<string[]>(loadPersistedProcessingIds())

  const setErrorMessage = useCallback((message: string) => setError(message), [])

  const reload = useCallback(async () => {
    if (!token) return
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
  }, [token])

  useEffect(() => {
    if (!token) return
    void reload()
  }, [token, reload])

  const onSelect = useCallback(
    async (resumeId: string) => {
      if (!token) return
      const target = resumes.find((resume) => resume.id === resumeId)
      if (target?.parse_status === 'processing') return
      setError('')
      if (target) setSelectedResume(target)
      try {
        const resume = await getResume(token, resumeId)
        setSelectedResume(resume)
        setResumes((prev) => replaceResume(prev, resume))
      } catch (err) {
        setErrorMessage((err as Error).message || String(err))
      }
    },
    [token, resumes, setErrorMessage],
  )

  const onUpload = useCallback(
    async (file: File | null) => {
      if (!file || !token) return
      if (resumes.filter((resume) => resume.parse_status === 'ready').length >= MAX_RESUME_COUNT) {
        setError(`最多 ${MAX_RESUME_COUNT} 份简历`)
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
          await reload()
        }
      } catch (err) {
        setResumes((prev) => prev.filter((resume) => resume.id !== processingResume.id))
        setErrorMessage((err as Error).message || String(err))
      } finally {
        setIsExtracting(false)
        const next = processingIdsRef.current.filter((id) => id !== processingResume.id)
        persistProcessingIds(next)
      }
    },
    [token, resumes, reload, setErrorMessage],
  )

  const onDelete = useCallback(
    async (resume: ResumeCardItem) => {
      if (!token) return
      if (resume.parse_status === 'processing') return
      setError('')
      setDeletingResumeId(resume.id)
      try {
        await deleteResume(token, resume.id)
        setResumes((prev) => prev.filter((item) => item.id !== resume.id))
        if (selectedResume?.id === resume.id) setSelectedResume(null)
      } catch (err) {
        setErrorMessage((err as Error).message || String(err))
      } finally {
        setDeletingResumeId('')
      }
    },
    [token, selectedResume, setErrorMessage],
  )

  return {
    resumes,
    selectedResume,
    isExtracting,
    deletingResumeId,
    error,
    reload,
    onSelect,
    onUpload,
    onDelete,
    setError,
  }
}
