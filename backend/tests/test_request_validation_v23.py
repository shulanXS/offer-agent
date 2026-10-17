"""v2.3 interview_language 字段补全测试。"""
from __future__ import annotations

import importlib
import time

import pytest
from fastapi.testclient import TestClient

from app.core import config as cfg
from app.db import store as store_mod
from app.main import app
from app.services.interview_planning.request_validation import validate_interview_configuration


@pytest.fixture
def fresh_db(monkeypatch, tmp_path):
    db_file = str(tmp_path / "lang.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    importlib.reload(cfg)
    importlib.reload(store_mod)
    store_mod.init_db()
    yield db_file


def test_interview_language_default_zh_en_validated() -> None:
    # 缺省 → en
    cfg_dict = validate_interview_configuration(
        {
            "resume_id": "r1",
            "interview_type": "experienced",
            "target_role": "backend",
            "target_level": "intermediate",
            "duration_minutes": 30,
            "focus_topics": ["python"],
        },
        trace_id="t",
    )
    assert cfg_dict["interview_language"] == "en"

    # 显式 zh
    cfg_dict = validate_interview_configuration(
        {
            "resume_id": "r1",
            "interview_type": "experienced",
            "target_role": "backend",
            "target_level": "intermediate",
            "duration_minutes": 30,
            "focus_topics": ["python"],
            "interview_language": "zh",
        },
        trace_id="t",
    )
    assert cfg_dict["interview_language"] == "zh"


def test_interview_language_invalid_value_rejected() -> None:
    from app.core.errors import ErrorCode

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        validate_interview_configuration(
            {
                "resume_id": "r1",
                "interview_type": "experienced",
                "target_role": "backend",
                "target_level": "intermediate",
                "duration_minutes": 30,
                "focus_topics": ["python"],
                "interview_language": "fr",
            },
            trace_id="t",
        )
    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == ErrorCode.INTERVIEW_LANGUAGE_INVALID


def test_create_interview_persists_interview_language(fresh_db) -> None:
    """create_interview 把 interview_language 写入 session.configuration。"""
    with TestClient(app) as client:
        uname = f"u_{int(time.time()*1000)%1_000_000}_lang"
        r = client.post(
            "/api/auth/register",
            json={"username": uname, "password": "secret123"},
        )
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 直接通过 store 造一个 resume（避免 prep 复杂）
        user = store_mod.Store().get_user_by_username(uname)
        store_mod.Store().create_resume(
            user_id=user["id"],
            filename="t.txt",
            payload={"content_type": "text/plain", "resume_text": "a" * 200},
        )
        # 用 service.create_interview（不调 LLM）
        from app.services.interview_planning_service import InterviewPlanningService

        svc = InterviewPlanningService()
        resumes = store_mod.Store().list_resumes(user["id"])
        result = svc.create_interview(
            user["id"],
            {
                "resume_id": resumes[0]["id"],
                "interview_type": "experienced",
                "target_role": "backend",
                "target_level": "intermediate",
                "duration_minutes": 30,
                "focus_topics": ["python"],
                "interview_language": "zh",
            },
        )
        # plan_preview 含 session_id，从 store 取出 session.configuration
        sid = result.get("session_id")
        assert sid is not None
        from app.db.store import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT configuration_json FROM interview_sessions WHERE id = ?", (sid,),
            ).fetchone()
        import json
        cfg = json.loads(row["configuration_json"])
        assert cfg["interview_language"] == "zh"
