import type { ResumeSummary } from '../types'

type ResumePreviewPanelProps = {
  resume: ResumeSummary
  updatedAtText: string
}

export function ResumePreviewPanel({ resume, updatedAtText }: ResumePreviewPanelProps) {
  return (
    <div className="resume-preview">
      <h4>{resume.filename}</h4>
      <div className="resume-preview-meta">
        <span>
          解析模型：{resume.model_provider || '未记录'} / {resume.model_name || '默认模型'}
        </span>
        <span>更新时间：{updatedAtText}</span>
      </div>
      <section className="resume-preview-section">
        <h5>个人摘要</h5>
        <p>{resume.personal_info || '暂无个人信息摘要'}</p>
      </section>
      <section className="resume-preview-section">
        <h5>亮点标签</h5>
        <div className="resume-chip-list">
          {resume.highlights.length > 0 ? (
            resume.highlights.map((item) => (
              <span key={item} className="resume-chip">
                {item}
              </span>
            ))
          ) : (
            <p>暂无</p>
          )}
        </div>
      </section>
      <section className="resume-preview-section">
        <h5>技术技能</h5>
        <div className="resume-chip-list">
          {resume.technical_skills.length > 0 ? (
            resume.technical_skills.map((item) => (
              <span key={item} className="resume-chip resume-chip-skill">
                {item}
              </span>
            ))
          ) : (
            <p>暂无</p>
          )}
        </div>
      </section>
      <section className="resume-preview-section">
        <h5>工作经历</h5>
        {resume.work_experience.length > 0 ? (
          <div className="resume-entry-list">
            {resume.work_experience.map((item, index) => (
              <article key={`${item.name}-${index}`} className="resume-entry-card">
                <strong>{item.name || `经历 ${index + 1}`}</strong>
                <p>{item.detail || '暂无详情'}</p>
              </article>
            ))}
          </div>
        ) : (
          <p>暂无</p>
        )}
      </section>
      <section className="resume-preview-section">
        <h5>项目经历</h5>
        {resume.project_experience.length > 0 ? (
          <div className="resume-entry-list">
            {resume.project_experience.map((item, index) => (
              <article key={`${item.name}-${index}`} className="resume-entry-card">
                <strong>{item.name || `项目 ${index + 1}`}</strong>
                <p>{item.detail || '暂无详情'}</p>
              </article>
            ))}
          </div>
        ) : (
          <p>暂无</p>
        )}
      </section>
      <details className="resume-raw-text">
        <summary>查看抽取原文</summary>
        <pre>{resume.resume_text || '暂无原文内容'}</pre>
      </details>
    </div>
  )
}
