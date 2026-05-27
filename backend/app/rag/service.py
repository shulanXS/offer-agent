import logging

from app.core.config import settings
from app.core.logging_utils import log_payload
from app.rag.embeddings import create_embedding_service
from app.rag.milvus_store import MilvusLiteStore
from app.rag.schemas import DOC_TYPE_LABELS, PlanningRAGContext, RetrievedChunk, normalize_role


logger = logging.getLogger("uvicorn.error")


class PlanningRAGService:
    def retrieve_for_planning(
        self,
        *,
        target_role: str,
        job_title: str,
        language: str,
        difficulty_level: str,
        technical_skills: list[str],
        highlights: list[str],
        resume_text: str,
        trace_id: str = "",
    ) -> PlanningRAGContext:
        if not settings.rag_enabled:
            return PlanningRAGContext()

        role_profile = normalize_role(target_role, job_title)
        if role_profile is None:
            logger.info(
                "[trace_id=%s] Planning RAG skipped because role normalization failed: target_role=%s job_title=%s",
                trace_id or "-",
                target_role or "-",
                job_title or "-",
            )
            return PlanningRAGContext()

        query = self._build_query(
            role_name=role_profile.display_name,
            language=language,
            difficulty_level=difficulty_level,
            technical_skills=technical_skills,
            highlights=highlights,
            resume_text=resume_text,
        )
        try:
            embedding_service = create_embedding_service()
            query_vector = embedding_service.embed_query(query)
            store = MilvusLiteStore()
            sources = store.search(query_vector=query_vector, role_slug=role_profile.slug, limit=settings.rag_top_k)
        except Exception:
            logger.exception(
                "[trace_id=%s] Planning RAG failed unexpectedly: role=%s",
                trace_id or "-",
                role_profile.display_name,
            )
            return PlanningRAGContext(
                role_slug=role_profile.slug,
                role_name=role_profile.display_name,
                query=query,
                focus_points=list(role_profile.default_focus_points),
            )

        context = self._pack_context(role_name=role_profile.display_name, sources=sources)
        if not sources:
            logger.warning(
                "[trace_id=%s] Planning RAG returned no hits: role=%s query=%s",
                trace_id or "-",
                role_profile.display_name,
                query,
            )
        result = PlanningRAGContext(
            role_slug=role_profile.slug,
            role_name=role_profile.display_name,
            query=query,
            context=context,
            focus_points=list(role_profile.default_focus_points),
            sources=sources,
        )
        logger.info(
            "[trace_id=%s] Planning RAG hits: role=%s count=%s hits=%s",
            trace_id or "-",
            role_profile.display_name,
            len(sources),
            [
                {
                    "doc_type": item.doc_type,
                    "section_title": item.section_title,
                    "source_path": item.source_path,
                    "score": item.score,
                }
                for item in sources
            ],
        )
        log_payload(logger, logging.INFO, "Planning RAG retrieval result", result.to_log_dict(), trace_id=trace_id)
        return result

    @staticmethod
    def _build_query(
        *,
        role_name: str,
        language: str,
        difficulty_level: str,
        technical_skills: list[str],
        highlights: list[str],
        resume_text: str,
    ) -> str:
        resume_excerpt = " ".join((resume_text or "").split())[:240]
        return "\n".join(
            [
                f"岗位: {role_name}",
                f"技术语言: {language or '不限'}",
                f"面试难度: {difficulty_level or '入门'}",
                f"简历亮点: {', '.join(highlights[:6]) or '暂无'}",
                f"技术技能: {', '.join(technical_skills[:8]) or '暂无'}",
                f"简历摘要: {resume_excerpt or '暂无'}",
                "检索目标: 岗位JD、必备技能、常见面试题、重点考察维度",
            ]
        )

    @staticmethod
    def _pack_context(*, role_name: str, sources: list[RetrievedChunk]) -> str:
        if not sources:
            return ""
        grouped: dict[str, list[RetrievedChunk]] = {}
        for source in sources:
            grouped.setdefault(source.doc_type, []).append(source)
        sections: list[str] = [f"岗位知识库命中角色：{role_name}"]
        for doc_type in ("jd", "skills", "questions", "rubric"):
            items = grouped.get(doc_type, [])
            if not items:
                continue
            lines = [f"{DOC_TYPE_LABELS.get(doc_type, doc_type)}："]
            for item in items:
                lines.append(f"- {item.section_title}")
                lines.append(item.content)
            sections.append("\n".join(lines))
        return "\n\n".join(section for section in sections if section.strip())[:3200]
