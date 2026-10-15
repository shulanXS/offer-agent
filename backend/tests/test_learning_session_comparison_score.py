"""域 2.4 验证：LearningContextResponse.previous_overall_score。"""
from __future__ import annotations

import importlib
import time
import uuid

import pytest

from app.db import store as store_mod
from app.db import transaction as tx_mod
from app.db.transaction import transaction


@pytest.fixture
def fresh_db(monkeypatch, tmp_path):
    db_file = str(tmp_path / "test.db")
    monkeypatch.setenv("PYTHONHASHSEED", "0")
    from app.core import config as cfg
    monkeypatch.setattr(cfg.settings, "database_path", db_file)
    importlib.reload(store_mod)
    importlib.reload(tx_mod)
    store_mod.init_db()
    yield db_file


def _insert_user(uid: int) -> None:
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO users (id, username, password_hash, quota_remaining, created_at, updated_at)
            VALUES (?, ?, 'h', 5, '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')
            """,
            (uid, f"u_{uid}"),
        )


def _insert_resume(uid: int, resume_id: str) -> None:
    ts = "2026-01-01T00:00:00+00:00"
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO resumes
                (id, user_id, filename, payload_json, created_at, updated_at)
            VALUES (?, ?, 'r1.txt', '{}', ?, ?)
            """,
            (resume_id, uid, ts, ts),
        )


def _insert_learning_profile(uid: int) -> None:
    ts = "2026-01-01T00:00:00+00:00"
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO user_learning_profiles
                (user_id, resume_id, target_role, interview_type, profile_json, updated_at)
            VALUES (?, 'r1', 'backend', 'experienced', '{}', ?)
            """,
            (uid, ts),
        )


def _insert_session(uid: int, sid: str, status: str = "completed", resume_id: str = "r1") -> None:
    ts = "2026-01-01T00:00:00+00:00"
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO interview_sessions
                (id, user_id, title, target_role, status, profile_json,
                 workflow_state_json, evaluation_json, resume_id, configuration_json,
                 confirmed_plan_id, version, created_at, updated_at)
            VALUES (?, ?, 'demo', 'backend', ?, '{}', '{}', NULL, ?, ?, NULL, 0, ?, ?)
            """,
            (
                sid, uid,
                status,
                resume_id,
                '{"interview_type": "experienced", "target_role": "backend", "resume_id": "r1"}',
                ts, ts,
            ),
        )


def test_learning_context_previous_overall_score_set(fresh_db, monkeypatch) -> None:
    monkeypatch.setattr("app.services.learning.query.Store", store_mod.Store)
    from app.services.learning import query as q

    user_id = int(time.time() * 1000) % 1_000_000 + 1
    _insert_user(user_id)
    _insert_resume(user_id, "r1")
    _insert_learning_profile(user_id)
    sid_a = str(uuid.uuid4())
    sid_b = str(uuid.uuid4())
    _insert_session(user_id, sid_a)
    _insert_session(user_id, sid_b)

    # 写两条 learning_outcomes：A 场有 overall_score 且 eligible，B 场无
    a_outcome = {
        "session_id": sid_a,
        "overall_score": 72,
        "topics": {"t1": {"discussed": True, "score": 4}},
        "session_summary": {
            "total_topics": 1,
            "discussed_topics": 1,
            "scored_topics": 1,
            "signal_coverage_rate": 0.5,
        },
    }
    b_outcome = {
        "session_id": sid_b,
        "overall_score": None,
        "topics": {"t1": {"discussed": True, "score": 3}},
        "session_summary": {
            "total_topics": 1,
            "discussed_topics": 1,
            "scored_topics": 1,
            "signal_coverage_rate": 0.5,
        },
    }
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO learning_session_outcomes
              (id, session_id, user_id, resume_id, target_role, interview_type,
               outcome_json, completed_at, deleted_at)
            VALUES (?, ?, ?, 'r1', 'backend', 'experienced', ?, '2026-01-02T00:00:00+00:00', NULL)
            """,
            (str(uuid.uuid4()), sid_a, user_id, __import__("json").dumps(a_outcome)),
        )
        conn.execute(
            """
            INSERT INTO learning_session_outcomes
              (id, session_id, user_id, resume_id, target_role, interview_type,
               outcome_json, completed_at, deleted_at)
            VALUES (?, ?, ?, 'r1', 'backend', 'experienced', ?, '2026-01-03T00:00:00+00:00', NULL)
            """,
            (str(uuid.uuid4()), sid_b, user_id, __import__("json").dumps(b_outcome)),
        )

    result = q.get_learning_context_for_session(user_id=user_id, session_id=sid_b)
    # B 场本身 overall_score=None → previous_overall_score 应取 A 场的 72
    assert result["previous_overall_score"] == 72.0


def test_learning_context_previous_overall_score_none_when_no_prev(fresh_db, monkeypatch) -> None:
    monkeypatch.setattr("app.services.learning.query.Store", store_mod.Store)
    from app.services.learning import query as q

    user_id = int(time.time() * 1000) % 1_000_000 + 2
    _insert_user(user_id)
    _insert_resume(user_id, "r1")
    _insert_learning_profile(user_id)
    sid = str(uuid.uuid4())
    _insert_session(user_id, sid)

    # 写一条 learning_outcome，无 prior session
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO learning_session_outcomes
              (id, session_id, user_id, resume_id, target_role, interview_type,
               outcome_json, completed_at, deleted_at)
            VALUES (?, ?, ?, 'r1', 'backend', 'experienced', ?, '2026-01-02T00:00:00+00:00', NULL)
            """,
            (str(uuid.uuid4()), sid, user_id, '{"overall_score": 80, "session_id": "%s"}' % sid),
        )

    result = q.get_learning_context_for_session(user_id=user_id, session_id=sid)
    assert result["previous_overall_score"] is None
