import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { CheckCircle2, Clock3, FileText, Info, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { ResumePreviewPanel } from '../components/ResumePreviewPanel'
import type { ResumeSummary } from '../types'
import { formatDateTime, formatResumeMeta, getResumeBadge, MAX_RESUME_COUNT, type ResumeCardItem } from '../utils/resume'

interface ResumesPageProps {
  error: string
  resumes: ResumeCardItem[]
  selectedResume: ResumeSummary | null
  isExtracting: boolean
  deletingResumeId: string
  onResumeSelect: (resumeId: string) => Promise<void>
  onResumeUpload: (file: File | null) => Promise<void>
  onResumeDelete: (resume: ResumeCardItem) => Promise<void>
}

export function ResumesPage({
  error,
  resumes,
  selectedResume,
  isExtracting,
  deletingResumeId,
  onResumeSelect,
  onResumeUpload,
  onResumeDelete,
}: ResumesPageProps) {
  const [deleteTarget, setDeleteTarget] = useState<ResumeCardItem | null>(null)

  function closeDeleteDialog() {
    if (!deletingResumeId) {
      setDeleteTarget(null)
    }
  }

  return (
    <>
      <header className="v2-page-header">
        <div>
          <div className="v2-title-row">
            <h2>我的简历</h2>
          </div>
          <p>管理用于 AI 面试官生成面试计划的候选人资料。</p>
        </div>
        <div className="v2-hero-art" aria-hidden="true">
          <div className="v2-hero-doc doc-a" />
          <div className="v2-hero-doc doc-b" />
          <div className="v2-hero-cube">AI</div>
        </div>
      </header>

      {error ? <p className="v2-error">{error}</p> : null}
      <section className="v2-resume-page">
        <div className="v2-resume-page-header">
          <h3>
            简历列表 <span>{resumes.length}/{MAX_RESUME_COUNT}</span>
          </h3>
        </div>
        <div className="v2-resume-grid">
          {resumes.map((resume) => (
            <Card
              key={resume.id}
              className={`v2-resume-card ${selectedResume?.id === resume.id ? 'active' : ''} ${
                resume.parse_status === 'processing' ? 'processing' : ''
              }`}
            >
              <div className="v2-resume-actions">
                <button
                  type="button"
                  className="v2-resume-card-delete"
                  aria-label={`删除 ${resume.filename}`}
                  disabled={deletingResumeId === resume.id || resume.parse_status === 'processing'}
                  onClick={() => setDeleteTarget(resume)}
                >
                  <Trash2 />
                </button>
                <Button
                  variant="outline"
                  size="sm"
                  className="v2-ghost-compact"
                  type="button"
                  disabled={resume.parse_status !== 'ready'}
                  onClick={() => void onResumeSelect(resume.id)}
                >
                  查看结果
                </Button>
              </div>
              <div className="v2-resume-card-icon">
                <FileText />
                <span className="v2-resume-badge">{getResumeBadge(resume.filename)}</span>
              </div>
              <div className="v2-resume-card-main">
                <strong>{resume.filename}</strong>
                <div className="v2-resume-skills">
                  {resume.parse_status === 'processing' ? (
                    <Badge variant="secondary">正在解析</Badge>
                  ) : resume.technical_skills.length > 0 ? (
                    resume.technical_skills.slice(0, 3).map((skill) => (
                      <Badge key={skill} variant="secondary">
                        {skill}
                      </Badge>
                    ))
                  ) : (
                    <Badge variant="secondary">暂无技能标签</Badge>
                  )}
                </div>
                <p>
                  <Clock3 />
                  {resume.parse_status === 'processing' ? '正在解析简历内容' : formatResumeMeta(resume)}
                </p>
              </div>
              <div className="v2-resume-card-footer">
                <div className="v2-resume-status">
                  {resume.parse_status === 'processing' ? (
                    <span className="v2-resume-spinner" aria-hidden="true" />
                  ) : (
                    <CheckCircle2 />
                  )}
                  <span>{resume.parse_status === 'processing' ? '解析中' : '已解析完成'}</span>
                </div>
              </div>
            </Card>
          ))}
          <Label className={`v2-resume-upload-card ${isExtracting ? 'disabled' : ''}`}>
            <input
              type="file"
              accept=".pdf,.txt,.md,.doc,.docx"
              disabled={isExtracting}
              onChange={(event) => {
                void onResumeUpload(event.target.files?.[0] ?? null)
                event.currentTarget.value = ''
              }}
            />
            <span className="v2-resume-upload-plus">
              <Plus />
            </span>
            <strong>{isExtracting ? '简历解析中...' : '添加简历'}</strong>
            <p>支持 PDF、DOC、DOCX、TXT、MD 格式</p>
          </Label>
        </div>
        {selectedResume ? (
          <div className="v2-resume-page-tip">
            当前查看：{selectedResume.filename}。这份简历已可用于后续面试配置。
          </div>
        ) : (
          <div className="v2-resume-page-tip">
            {resumes.length === 0 ? '请先上传一份简历。' : '点击“查看结果”查看简历解析摘要。'}
          </div>
        )}
        {selectedResume ? (
          <ResumePreviewPanel resume={selectedResume} updatedAtText={formatDateTime(selectedResume.updated_at)} />
        ) : null}
        <div className="v2-resume-hint">
          <Info />
          点击“查看结果”查看简历解析摘要。
        </div>
      </section>
      <AlertDialog open={Boolean(deleteTarget)} onOpenChange={(open) => (!open ? closeDeleteDialog() : undefined)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除简历</AlertDialogTitle>
            <AlertDialogDescription>
              确定删除简历“{deleteTarget?.filename}”吗？删除后不能继续使用这份简历。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={Boolean(deletingResumeId)}>取消</AlertDialogCancel>
            <AlertDialogAction
              className="v2-dialog-confirm"
              disabled={Boolean(deletingResumeId)}
              onClick={(event) => {
                event.preventDefault()
                if (!deleteTarget) return
                void onResumeDelete(deleteTarget).then(() => setDeleteTarget(null))
              }}
            >
              {deletingResumeId ? '处理中...' : '确定'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
