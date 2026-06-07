from __future__ import annotations

from typing import Any

from app.rag.schemas import PlanningRAGContext, RetrievedChunk
from app.services.interview_planning.context import get_planning_context


def _sample_configuration(*, target_role: str = "backend") -> dict[str, Any]:
    return {
        "interview_type": "experienced",
        "target_role": target_role,
        "language": "java",
        "target_level": "intermediate",
        "focus_topics": ["项目深挖"],
        "jd_text": "",
    }


def _sample_resume() -> dict[str, Any]:
    return {
        "resume_text": "候选人拥有三年 Java 后端经验，负责订单系统重构。",
        "highlights": ["订单系统"],
        "technical_skills": ["Java", "Redis"],
        "personal_info": "张三",
    }


def test_get_planning_context_returns_empty_when_rag_disabled(monkeypatch) -> None:
    monkeypatch.setattr("app.core.config.settings.rag_enabled", False)

    context = get_planning_context(
        configuration=_sample_configuration(),
        resume=_sample_resume(),
        trace_id="trace-rag-off",
    )

    assert context["role_knowledge_context"] == ""
    assert context["planning_rag_sources"] == []


def test_get_planning_context_uses_planning_rag_service(monkeypatch) -> None:
    monkeypatch.setattr("app.core.config.settings.rag_enabled", True)
    captured: dict[str, Any] = {}

    def fake_retrieve_for_planning(**kwargs: Any) -> PlanningRAGContext:
        captured.update(kwargs)
        return PlanningRAGContext(
            role_slug="backend_engineer",
            role_name="后端开发工程师",
            context="岗位知识库命中角色：后端开发工程师\n必备技能：\n- Redis",
            sources=[
                RetrievedChunk(
                    id="chunk-1",
                    role_slug="backend_engineer",
                    role_name="后端开发工程师",
                    doc_type="skills",
                    section_title="Redis",
                    content="缓存与持久化",
                    source_path="roles/backend_engineer.md",
                    score=0.91,
                )
            ],
        )

    monkeypatch.setattr(
        "app.services.interview_planning.context._planning_rag.retrieve_for_planning",
        fake_retrieve_for_planning,
    )

    context = get_planning_context(
        configuration=_sample_configuration(target_role="backend"),
        resume=_sample_resume(),
        trace_id="trace-rag-on",
    )

    assert "Redis" in context["role_knowledge_context"]
    assert len(context["planning_rag_sources"]) == 1
    assert captured["target_role"] == "后端开发工程师"
    assert captured["job_title"] == "后端开发工程师"
    assert captured["language"] == "Java"
    assert captured["difficulty_level"] == "进阶"
    assert captured["trace_id"] == "trace-rag-on"
    assert captured["resume_text"].startswith("候选人拥有三年")
