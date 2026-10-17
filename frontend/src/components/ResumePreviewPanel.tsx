import type { ResumeSummary } from '../types'
import { useTranslation } from 'react-i18next'

type ResumePreviewPanelProps = {
  resume: ResumeSummary
  updatedAtText: string
}

export function ResumePreviewPanel({ resume, updatedAtText }: ResumePreviewPanelProps) {
  const { t } = useTranslation('resumes')
  const empty = t('preview_empty_text')
  return (
    <div className="resume-preview">
      <h4>{resume.filename}</h4>
      <div className="resume-preview-meta">
        <span>
          {t('preview_model_label')}：{resume.model_provider || t('preview_model_unrecorded')} / {resume.model_name || t('preview_model_default')}
        </span>
        <span>{t('preview_updated_at')}：{updatedAtText}</span>
      </div>
      <section className="resume-preview-section">
        <h5>{t('preview_personal_summary')}</h5>
        <p>{resume.personal_info || empty}</p>
      </section>
      <section className="resume-preview-section">
        <h5>{t('preview_highlights')}</h5>
        <div className="resume-chip-list">
          {resume.highlights.length > 0 ? (
            resume.highlights.map((item) => (
              <span key={item} className="resume-chip">
                {item}
              </span>
            ))
          ) : (
            <p>{empty}</p>
          )}
        </div>
      </section>
      <section className="resume-preview-section">
        <h5>{t('preview_skills')}</h5>
        <div className="resume-chip-list">
          {resume.technical_skills.length > 0 ? (
            resume.technical_skills.map((item) => (
              <span key={item} className="resume-chip resume-chip-skill">
                {item}
              </span>
            ))
          ) : (
            <p>{empty}</p>
          )}
        </div>
      </section>
      <section className="resume-preview-section">
        <h5>{t('preview_work')}</h5>
        {resume.work_experience.length > 0 ? (
          <div className="resume-entry-list">
            {resume.work_experience.map((item, index) => (
              <article key={`${item.name}-${index}`} className="resume-entry-card">
                <strong>{item.name || t('preview_fallback_name', { n: index + 1 })}</strong>
                <p>{item.detail || t('preview_no_detail')}</p>
              </article>
            ))}
          </div>
        ) : (
          <p>{empty}</p>
        )}
      </section>
      <section className="resume-preview-section">
        <h5>{t('preview_projects')}</h5>
        {resume.project_experience.length > 0 ? (
          <div className="resume-entry-list">
            {resume.project_experience.map((item, index) => (
              <article key={`${item.name}-${index}`} className="resume-entry-card">
                <strong>{item.name || t('preview_fallback_name', { n: index + 1 })}</strong>
                <p>{item.detail || t('preview_no_detail')}</p>
              </article>
            ))}
          </div>
        ) : (
          <p>{empty}</p>
        )}
      </section>
      <details className="resume-raw-text">
        <summary>{t('preview_raw_text')}</summary>
        <pre>{resume.resume_text || empty}</pre>
      </details>
    </div>
  )
}
