"""域 3.4 验证：配额审计 + 补偿。"""
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


def _insert_user(uid: int, quota: int = 5) -> None:
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO users (id, username, password_hash, quota_remaining, created_at, updated_at)
            VALUES (?, ?, 'h', ?, '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')
            """,
            (uid, f"u_{uid}", quota),
        )


def test_decrement_writes_audit(fresh_db) -> None:
    user_id = int(time.time() * 1000) % 1_000_000 + 1
    _insert_user(user_id, 5)
    store = store_mod.Store()
    store.decrement_quota(user_id, session_id="s1", reason="interview_activate")
    user = store.get_user_by_id(user_id)
    assert user["quota_remaining"] == 4
    with transaction() as conn:
        row = conn.execute(
            "SELECT * FROM quota_audit WHERE user_id = ? AND session_id = ?",
            (user_id, "s1"),
        ).fetchone()
        assert row is not None
        assert row["delta"] == -1
        assert row["reason"] == "interview_activate"


def test_compensate_quota_increments(fresh_db) -> None:
    user_id = int(time.time() * 1000) % 1_000_000 + 2
    _insert_user(user_id, 5)
    store = store_mod.Store()
    store.decrement_quota(user_id, session_id="s2")
    store.compensate_quota(user_id, session_id="s2", reason="rollback")
    user = store.get_user_by_id(user_id)
    assert user["quota_remaining"] == 5
    with transaction() as conn:
        rows = conn.execute(
            "SELECT delta FROM quota_audit WHERE user_id = ? AND session_id = ? ORDER BY id",
            (user_id, "s2"),
        ).fetchall()
        deltas = [r["delta"] for r in rows]
        assert deltas == [-1, 1]


def test_audit_outcome_for_session_orphan_rolls_back(fresh_db) -> None:
    """已 decrement 但无 outcome → 评估完成时回滚。"""
    user_id = int(time.time() * 1000) % 1_000_000 + 3
    _insert_user(user_id, 5)
    store = store_mod.Store()
    sid = str(uuid.uuid4())
    store.decrement_quota(user_id, session_id=sid)
    assert store.get_user_by_id(user_id)["quota_remaining"] == 4
    # 评估完成时调用：没有 outcome，应回滚
    store.audit_outcome_for_session(sid)
    assert store.get_user_by_id(user_id)["quota_remaining"] == 5


def test_audit_outcome_for_session_with_outcome_no_op(fresh_db) -> None:
    """已有 outcome 的不应回滚。"""
    user_id = int(time.time() * 1000) % 1_000_000 + 4
    _insert_user(user_id, 5)
    store = store_mod.Store()
    sid = str(uuid.uuid4())
    store.decrement_quota(user_id, session_id=sid)
    # 模拟 outcome 已存在
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO learning_session_outcomes
              (id, session_id, user_id, resume_id, target_role, interview_type,
               outcome_json, completed_at, deleted_at)
            VALUES (?, ?, ?, 'r', 'backend', 'experienced', '{"overall_score": 70}', '2026-01-02T00:00:00+00:00', NULL)
            """,
            (str(uuid.uuid4()), sid, user_id),
        )
    store.audit_outcome_for_session(sid)
    # 仍为 4（不应回滚）
    assert store.get_user_by_id(user_id)["quota_remaining"] == 4
