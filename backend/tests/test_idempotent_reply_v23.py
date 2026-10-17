"""v2.3 reply 幂等按 seq 配对测试。"""
from __future__ import annotations

import importlib
import time

import pytest

from app.core import config as cfg
from app.db import store as store_mod


@pytest.fixture
def fresh_db(monkeypatch, tmp_path):
    db_file = str(tmp_path / "idempotent.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    importlib.reload(cfg)
    importlib.reload(store_mod)
    store_mod.init_db()
    yield db_file


def test_find_message_pair_by_request_id_pairs_by_seq(fresh_db) -> None:
    store = store_mod.Store()
    user = store.create_user(
        username=f"u_{int(time.time()*1000)%1_000_000}_idem",
        password_hash="x",
        quota_remaining=10,
    )
    sid = _create_session(store, user["id"])
    # 在事务内写 user + assistant 消息（与生产路径一致）
    with store_mod.get_connection() as conn:
        store.create_message_in_conn(
            conn,
            session_id=sid,
            role="user",
            kind="answer",
            content="hello",
            request_id="req-1",
        )
        conn.commit()
    user_msg = store.find_message_by_request_id(sid, "req-1")
    assert user_msg is not None
    seq = user_msg["seq"]
    with store_mod.get_connection() as conn:
        store.create_message_in_conn(
            conn,
            session_id=sid,
            role="assistant",
            kind="interviewer",
            content="world",
        )
        conn.commit()
    # 配对查找
    u, a = store.find_message_pair_by_request_id(sid, "req-1")
    assert u is not None and a is not None
    assert u["seq"] == seq
    assert a["seq"] == seq + 1
    assert a["content"] == "world"


def test_find_message_pair_returns_none_for_missing(fresh_db) -> None:
    store = store_mod.Store()
    user = store.create_user(
        username=f"u_{int(time.time()*1000)%1_000_000}_idem2",
        password_hash="x",
        quota_remaining=10,
    )
    sid = _create_session(store, user["id"])
    u, a = store.find_message_pair_by_request_id(sid, "never")
    assert u is None and a is None


def test_find_message_pair_no_assistant_yet(fresh_db) -> None:
    store = store_mod.Store()
    user = store.create_user(
        username=f"u_{int(time.time()*1000)%1_000_000}_idem3",
        password_hash="x",
        quota_remaining=10,
    )
    sid = _create_session(store, user["id"])
    with store_mod.get_connection() as conn:
        store.create_message_in_conn(
            conn,
            session_id=sid,
            role="user",
            kind="answer",
            content="hi",
            request_id="req-2",
        )
        conn.commit()
    u, a = store.find_message_pair_by_request_id(sid, "req-2")
    assert u is not None
    assert a is None


def _create_session(store: store_mod.Store, user_id: int) -> str:
    """v2.3 helper：直接 INSERT 一条 session（store 缺公开 create_session）。"""
    import uuid
    from app.db.store import get_connection
    sid = f"sess-{uuid.uuid4().hex[:8]}"
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO interview_sessions (id, user_id, title, target_role, status, profile_json, workflow_state_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))",
            (sid, user_id, "test", "backend", "active", "{}", "{}"),
        )
        conn.commit()
    return sid
