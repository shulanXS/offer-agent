"""域 4.2 验证：update_session / update_planning_session 白名单列名 + 防止 SQL 注入。"""
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


def _insert_session(uid: int, sid: str) -> None:
    ts = "2026-01-01T00:00:00+00:00"
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO interview_sessions
                (id, user_id, title, target_role, status, profile_json,
                 workflow_state_json, evaluation_json, resume_id, configuration_json,
                 confirmed_plan_id, version, created_at, updated_at)
            VALUES (?, ?, 'demo', 'backend', 'plan_confirmed', '{}', '{}', NULL, NULL, ?, NULL, 0, ?, ?)
            """,
            (sid, uid, '{"interview_type": "experienced"}', ts, ts),
        )


def test_update_session_with_injection_payload_does_not_execute(fresh_db) -> None:
    """status 传入 SQL 注入 payload，不应被执行（仍按字符串存）。"""
    user_id = int(time.time() * 1000) % 1_000_000 + 1
    _insert_user(user_id)
    sid = str(uuid.uuid4())
    _insert_session(user_id, sid)

    store = store_mod.Store()
    # 注入 payload：' DROP TABLE users;--' 作为 status 字符串值
    injection = "x'; DROP TABLE users;--"
    store.update_session(sid, status=injection)

    record = store.get_interview_session_record(user_id, sid)
    assert record["status"] == injection  # 整段作为字符串
    # users 表仍存在
    user = store.get_user_by_id(user_id)
    assert user is not None


def test_update_session_status_normal(fresh_db) -> None:
    user_id = int(time.time() * 1000) % 1_000_000 + 2
    _insert_user(user_id)
    sid = str(uuid.uuid4())
    _insert_session(user_id, sid)
    store = store_mod.Store()
    store.update_session(sid, status="active")
    record = store.get_interview_session_record(user_id, sid)
    assert record["status"] == "active"


def test_unknown_column_raises(fresh_db) -> None:
    """_assert_known_column 应拒绝未知列名（防御性，外部无法触发但保证不变量）。"""
    from app.db.store import _assert_known_column
    with pytest.raises(ValueError):
        _assert_known_column("interview_sessions", "evil_column")
