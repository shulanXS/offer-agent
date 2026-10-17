"""v2.3 评估分布式锁测试。

覆盖：
- 同一 session_id 并发两次 evaluate，只生成 1 份 evaluation
- 第二个调用在已有 evaluation 时直接返回
"""
from __future__ import annotations

import importlib
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core import config as cfg
from app.db import store as store_mod
from app.main import app
from app.services.events import bus, evaluation_channel


@pytest.fixture
def fresh_db(monkeypatch, tmp_path):
    db_file = str(tmp_path / "eval_lock.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    importlib.reload(cfg)
    importlib.reload(store_mod)
    store_mod.init_db()
    yield db_file


def _register_and_login(client: TestClient, username: str, password: str = "secret123") -> str:
    r = client.post("/api/auth/register", json={"username": username, "password": password})
    assert r.status_code == 200
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _mock_evaluation(self, record, *, trace_id):
    return {
        "version": 1,
        "source": "mock",
        "summary": "mocked",
        "candidate_review": {
            "headline": "",
            "summary": "",
            "highlights": [],
            "weaknesses": [],
            "suggestions": [],
            "coverage_note": "",
            "overall_score_label": "综合得分",
        },
        "overall_score": 4,
        "coverage_rate": 1.0,
        "overall_confidence": 1.0,
        "coverage": {
            "completed_topic_count": 0,
            "total_topic_count": 0,
            "topics_with_evidence_count": 0,
            "scored_topic_count": 0,
            "discussed_topic_count": 0,
        },
        "competencies": [],
        "jd_match": None,
        "question_reviews": [],
        "practice_recommendations": [],
        "strengths": [],
        "risks": [],
        "unverified_items": [],
        "model_info": None,
    }


def test_concurrent_evaluate_keeps_single_evaluation(monkeypatch, fresh_db) -> None:
    """并发 evaluate：第二个调用在已有 evaluation record 时直接返回。"""
    # mock LLM：第一次调用前手动塞一条 evaluation 进 store
    monkeypatch.setattr(
        "app.services.interview_evaluation_service.InterviewEvaluationService._generate_report",
        _mock_evaluation,
    )

    with TestClient(app) as client:
        token = _register_and_login(client, f"u_{int(time.time()*1000)%1_000_000}_lock")
        # 准备一个 evaluating session（直接 INSERT，store 缺公开 create_session）
        import uuid
        import json as _json
        store = store_mod.Store()
        me = client.get("/api/auth/me", headers=_auth(token)).json()
        sid = f"sess-{uuid.uuid4().hex[:8]}"
        with store_mod.get_connection() as conn:
            conn.execute(
                "INSERT INTO interview_sessions (id, user_id, title, target_role, status, profile_json, workflow_state_json, configuration_json, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))",
                (sid, me["id"], "t", "backend", "evaluating", "{}", "{}", _json.dumps({"interview_language": "en"})),
            )
            conn.commit()
        store.update_session(sid, status="evaluating")

        # 1) 第一次调用
        r1 = client.post(f"/api/interviews/{sid}/evaluate", headers=_auth(token))
        assert r1.status_code == 200, r1.text
        body1 = r1.json()

        # 2) 第二次调用 → 应当直接拿到同一份 evaluation（无新生成）
        r2 = client.post(f"/api/interviews/{sid}/evaluate", headers=_auth(token))
        assert r2.status_code == 200, r2.text
        body2 = r2.json()
        # 两次 evaluation 应当一致
        assert body1["evaluation"] == body2["evaluation"]


def test_evaluation_publishes_sse_event(monkeypatch, fresh_db) -> None:
    """评估完成 → bus 推 evaluation_done 事件"""
    monkeypatch.setattr(
        "app.services.interview_evaluation_service.InterviewEvaluationService._generate_report",
        _mock_evaluation,
    )

    with TestClient(app) as client:
        token = _register_and_login(client, f"u_{int(time.time()*1000)%1_000_000}_ev")
        store = store_mod.Store()
        me = client.get("/api/auth/me", headers=_auth(token)).json()
        import uuid
        import json as _json
        sid = f"sess-{uuid.uuid4().hex[:8]}"
        with store_mod.get_connection() as conn:
            conn.execute(
                "INSERT INTO interview_sessions (id, user_id, title, target_role, status, profile_json, workflow_state_json, configuration_json, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))",
                (sid, me["id"], "t", "backend", "evaluating", "{}", "{}", _json.dumps({"interview_language": "en"})),
            )
            conn.commit()
        store.update_session(sid, status="evaluating")

        # 订阅 channel
        import asyncio

        async def _sub():
            q = await bus.subscribe(evaluation_channel(sid))
            return q

        loop_q: list[Any] = []

        async def _runner():
            loop_q.append(await _sub())
            # 触发 evaluate
            client.post(f"/api/interviews/{sid}/evaluate", headers=_auth(token))
            # 等待事件
            q = loop_q[0]
            ev = await asyncio.wait_for(q.get(), timeout=3.0)
            return ev

        ev = asyncio.run(_runner())
        assert ev["type"] == "evaluation_done"
        assert ev["session_id"] == sid
