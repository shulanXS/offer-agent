"""Planning 上下文：为 Agent 组装简历、JD、岗位知识等生成所需上下文。"""
from __future__ import annotations

from typing import Any

from app.rag.service import PlanningRAGService
from app.services.interview_configuration_service import configuration_labels

_planning_rag = PlanningRAGService()

# V2 配置枚举 → normalize_role / 知识库可识别的岗位名
_V2_ROLE_RAG_TITLE: dict[str, str] = {
    "backend": "后端开发工程师",
    "frontend": "前端开发工程师",
}


def _string_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def _resume_text(resume: dict[str, Any]) -> str:
    text = str(resume.get("resume_text") or "").strip()
    if text:
        return text
    parts: list[str] = []
    personal = str(resume.get("personal_info") or "").strip()
    if personal:
        parts.append(personal)
    parts.extend(_string_list(resume.get("highlights")))
    parts.extend(_string_list(resume.get("technical_skills")))
    return " ".join(parts)


def get_planning_context(
    *,
    configuration: dict[str, Any],
    resume: dict[str, Any],
    trace_id: str = "",
) -> dict[str, Any]:
    labels = configuration_labels(configuration)
    role_value = str(configuration.get("target_role") or "").strip()
    job_title = _V2_ROLE_RAG_TITLE.get(role_value, labels.get("target_role_label", ""))

    rag = _planning_rag.retrieve_for_planning(
        target_role=job_title,
        job_title=job_title,
        language=labels.get("language_label", ""),
        difficulty_level=labels.get("target_level_label", ""),
        technical_skills=_string_list(resume.get("technical_skills")),
        highlights=_string_list(resume.get("highlights")),
        resume_text=_resume_text(resume),
        trace_id=trace_id,
    )
    return {
        "role_knowledge_context": rag.context,
        "planning_rag_sources": [item.to_log_dict() for item in rag.sources],
    }
