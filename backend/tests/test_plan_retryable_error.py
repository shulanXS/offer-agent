"""v1.1 F4: 计划生成失败可重试 — API 返回结构化 retryable_error，前端可换模型。"""
from __future__ import annotations

import os
from typing import Any

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def failing_plan_client(monkeypatch: pytest.MonkeyPatch, tmp_path) -> TestClient:
    """Force the planning LLM to fail; ensure F4 retryable error is surfaced."""
    from app.core.config import settings
    from app.db.store import init_db
    from app.main import app
    from tests.support.llm_fake import FailingLLMClient, patch_failing_llm_client

    # Ensure the new v1.1 F4 path is taken (not the v1.0 template fallback).
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("OFFER_AGENT_PLAN_FALLBACK_TO_TEMPLATE", "0")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "f4.db"))
    monkeypatch.setattr(settings, "llm_provider", "openai", raising=False)
    monkeypatch.setattr(settings, "llm_model", "gpt-4o-mini", raising=False)
    monkeypatch.setattr(settings, "database_path", str(tmp_path / "f4.db"), raising=False)
    patch_failing_llm_client(monkeypatch, client=FailingLLMClient())

    init_db()
    return TestClient(app)


def _seed_user_with_resume(client: TestClient) -> dict[str, Any]:
    """Register a user and create a resume row directly via the store,
    bypassing the LLM extract endpoint."""
    r = client.post(
        "/api/auth/register",
        json={"username": "f4tester", "password": "secret123"},
    )
    assert r.status_code == 200, r.text
    user = r.json()["user"]
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    from app.db.store import Store
    store = Store()
    resume = store.create_resume(
        user_id=user["id"],
        filename="seed.txt",
        payload={
            "personal_info": "张三，Java 后端开发",
            "highlights": ["主导订单系统重构"],
            "technical_skills": ["Java", "Spring"],
            "resume_text": "张三，3 年 Java 后端，熟悉 Spring、Kafka、MySQL。",
            "work_experience": [{"name": "某科技公司", "detail": "负责订单系统后端开发"}],
            "project_experience": [{"name": "订单系统", "detail": "高并发订单处理"}],
            "model_provider": "openai",
            "model_name": "",
        },
    )
    return {"headers": headers, "user_id": user["id"], "resume_id": resume["id"]}


def _create_planning_session_directly(ctx: dict[str, Any]) -> str:
    """Create a planning session in 'planning' state via the store, so the
    /api/interviews/{id}/plan/generate endpoint can be tested in isolation
    without going through POST /api/interviews (which also triggers LLM)."""
    from app.db.store import Store
    store = Store()
    session = store.create_planning_session(
        user_id=ctx["user_id"],
        title="后端开发 面试",
        target_role="backend",
        resume_id=ctx["resume_id"],
        configuration={
            "resume_id": ctx["resume_id"],
            "interview_type": "experienced",
            "target_role": "backend",
            "language": "java",
            "target_level": "intermediate",
            "duration_minutes": 45,
            "focus_topics": ["项目深挖"],
            "jd_text": "",
            "interview_language": "zh",
        },
    )
    return session["id"]


def test_generate_plan_returns_retryable_error(failing_plan_client: TestClient):
    client = failing_plan_client
    ctx = _seed_user_with_resume(client)
    session_id = _create_planning_session_directly(ctx)
    r = client.post(
        f"/api/interviews/{session_id}/plan/generate",
        headers=ctx["headers"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    err = body.get("retryable_error")
    assert err is not None, body
    assert err["code"] == "PLAN_GENERATION_FAILED"
    assert err["retryable"] is True
    assert "重试" in err["message"] or "failed" in err["message"].lower()


def test_regenerate_plan_returns_retryable_error(failing_plan_client: TestClient):
    client = failing_plan_client
    ctx = _seed_user_with_resume(client)
    session_id = _create_planning_session_directly(ctx)
    # Flip to plan_ready and seed a plan so regenerate is allowed
    from app.db.store import Store
    store = Store()
    store.update_planning_session(session_id=session_id, status="plan_ready")
    store.create_interview_plan(
        session_id=session_id,
        version=1,
        status="ready",
        plan_json={"topics": [], "generation_meta": {"source": "seed", "degraded": True}},
        candidate_summary_json={"focus_topics": [], "reference_summary": []},
    )
    r = client.post(
        f"/api/interviews/{session_id}/plan/regenerate",
        headers=ctx["headers"],
        json={"regeneration_strategy": "different_plan", "additional_instruction": "再深一点"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    err = body.get("retryable_error")
    assert err is not None, body
    assert err["retryable"] is True
