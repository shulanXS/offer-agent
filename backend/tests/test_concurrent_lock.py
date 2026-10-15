"""域 1.3 验证：session_locks 分布式锁 + 事务原子性。"""
from __future__ import annotations

import importlib
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.db.store import Store
from app.db.transaction import transaction


@pytest.fixture
def fresh_db(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """每测试一个独立 SQLite 文件，避免状态污染。"""
    db_file = str(tmp_path / "test.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    from app.core import config as cfg

    importlib.reload(cfg)
    from app.db import store as store_mod

    importlib.reload(store_mod)
    from app.db import transaction as tx_mod

    importlib.reload(tx_mod)
    store_mod.init_db()
    yield db_file


def init_in_process(db_file: str) -> None:
    """复刻 init_db 的表结构但连接到 fresh 文件。"""
    from app.db.store import init_db
    init_db()


def _new_session(store: Store, *, user_id: int = 1, session_id: str | None = None) -> str:
    session_id = session_id or str(uuid.uuid4())
    ts = "2026-01-01T00:00:00+00:00"
    with transaction() as conn:
        existing = conn.execute(
            "SELECT id FROM interview_sessions WHERE id=?", (session_id,),
        ).fetchone()
        if existing is None:
            conn.execute(
                """
                INSERT INTO interview_sessions
                    (id, user_id, title, target_role, status, profile_json,
                     workflow_state_json, evaluation_json, resume_id, configuration_json,
                     confirmed_plan_id, version, created_at, updated_at)
                VALUES (?, ?, 'demo', 'backend', 'active', '{}', '{}', NULL, NULL, '{}', NULL, 0, ?, ?)
                """,
                (session_id, user_id, ts, ts),
            )
    return session_id


def test_acquire_releases_conflict_cycle(fresh_db) -> None:
    store = Store()
    sid = _new_session(store)

    a = store.acquire_session_lock(sid, lock_token="tok-A", ttl_seconds=60)
    assert a and a.get("lock_token") == "tok-A"

    # 异 token 冲突
    conflict = store.acquire_session_lock(sid, lock_token="tok-B", ttl_seconds=60)
    assert conflict and conflict.get("locked") is True

    # 同 token 幂等
    same = store.acquire_session_lock(sid, lock_token="tok-A", ttl_seconds=60)
    assert same and same.get("lock_token") == "tok-A"

    # release 后可被新 token 抢
    assert store.release_session_lock(sid, lock_token="tok-A") is True
    b = store.acquire_session_lock(sid, lock_token="tok-B", ttl_seconds=60)
    assert b and b.get("lock_token") == "tok-B"


def test_eight_threads_only_one_succeeds(fresh_db) -> None:
    store = Store()
    sid = _new_session(store)
    barrier = threading.Barrier(8)
    results: list = [None] * 8
    lock = threading.Lock()

    def worker(i: int) -> None:
        barrier.wait()
        token = f"tok-{i}"
        res = store.acquire_session_lock(sid, lock_token=token, ttl_seconds=60)
        with lock:
            results[i] = res

    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(worker, range(8)))

    winners = [r for r in results if r and r.get("lock_token") and not r.get("locked")]
    losers = [r for r in results if r and r.get("locked")]
    assert len(winners) == 1, f"winners={winners}, losers={losers}"
    assert len(losers) == 7


def test_release_on_failure_keeps_lock_releasable(fresh_db) -> None:
    store = Store()
    sid = _new_session(store)
    a = store.acquire_session_lock(sid, lock_token="t-A", ttl_seconds=60)
    assert a and a.get("lock_token") == "t-A"
    # 异常路径：service 应在 finally 释放
    try:
        raise RuntimeError("simulated handler failure")
    except RuntimeError:
        pass
    assert store.release_session_lock(sid, lock_token="t-A") is True
    # 释放后可被新 token 抢
    b = store.acquire_session_lock(sid, lock_token="t-B", ttl_seconds=60)
    assert b and b.get("lock_token") == "t-B"


def test_quota_decrement_writes_audit(fresh_db) -> None:
    store = Store()
    import time
    user_id = int(time.time() * 1000) % 1_000_000 + 100
    # 直接用 transaction 验证
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO users (id, username, password_hash, quota_remaining, created_at, updated_at)
            VALUES (?, ?, 'h', 3, '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')
            """,
            (user_id, f"auditor_{user_id}"),
        )
    user = store.decrement_quota(user_id, session_id="s1", reason="test")
    assert user and user["quota_remaining"] == 2

    # audit 表应记录 -1
    with transaction() as conn:
        row = conn.execute(
            "SELECT delta, reason FROM quota_audit WHERE user_id=? ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    assert row["delta"] == -1
    assert row["reason"] == "test"
