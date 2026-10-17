"""v2.3 用户额度与订阅状态机单源测试。

覆盖：
- 订阅有效时 `quota_remaining` 为 None（=无限）
- 过期后 sync_subscription_status 把 tier 降级为 free
- apply_payment_to_user(single) 在 expired_subscription 上升级为 paid
"""
from __future__ import annotations

import importlib
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core import config as cfg
from app.db import store as store_mod
from app.main import app


@pytest.fixture
def fresh_db(monkeypatch, tmp_path):
    db_file = str(tmp_path / "billing_v23.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    importlib.reload(cfg)
    importlib.reload(store_mod)
    store_mod.init_db()
    yield db_file


def _register_and_login(client: TestClient, username: str, password: str = "secret123") -> str:
    response = client.post(
        "/api/auth/register",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_subscription_active_returns_none_quota(fresh_db) -> None:
    with TestClient(app) as client:
        token = _register_and_login(client, f"u_{int(time.time()*1000)%1_000_000}_v23_a")
        r = client.post(
            "/api/billing/recharge",
            headers=_auth(token),
            json={"package": "subscription"},
        )
        assert r.status_code == 200, r.text
        me = client.get("/api/auth/me", headers=_auth(token)).json()
        # v2.3: 订阅有效 → quota_remaining = None
        assert me["quota_remaining"] is None
        assert me["tier"] == "subscription"
        assert me["membership_status"] == "active_subscription"


def test_sync_subscription_status_downgrades_on_expiry(fresh_db) -> None:
    """把 subscription_expires_at 写到过去 → sync 后 tier 降级"""
    store = store_mod.Store()
    with TestClient(app) as client:
        token = _register_and_login(client, f"u_{int(time.time()*1000)%1_000_000}_v23_b")
        client.post(
            "/api/billing/recharge",
            headers=_auth(token),
            json={"package": "subscription"},
        )
        me = client.get("/api/auth/me", headers=_auth(token)).json()
        assert me["quota_remaining"] is None
        # 直接改库把 expires 写到过去
        with store_mod.get_connection() as conn:
            past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
            conn.execute(
                "UPDATE users SET subscription_expires_at = ? WHERE username = ?",
                (past, me["username"]),
            )
            conn.commit()
        # 触发 sync
        synced = store.sync_subscription_status(me["id"])
        assert synced is not None
        assert synced["tier"] == "free"
        assert synced["membership_status"] == "expired_subscription"
        # 再次 me 应反映降级
        me2 = client.get("/api/auth/me", headers=_auth(token)).json()
        assert me2["tier"] == "free"
        assert me2["membership_status"] == "expired_subscription"
        # quota 应真实（非 None）
        assert isinstance(me2["quota_remaining"], int)


def test_single_recharge_after_subscription_expiry_paid(fresh_db) -> None:
    """订阅过期 → single 充值应升为 paid"""
    store = store_mod.Store()
    with TestClient(app) as client:
        token = _register_and_login(client, f"u_{int(time.time()*1000)%1_000_000}_v23_c")
        client.post(
            "/api/billing/recharge",
            headers=_auth(token),
            json={"package": "subscription"},
        )
        me = client.get("/api/auth/me", headers=_auth(token)).json()
        # 写过期
        with store_mod.get_connection() as conn:
            past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
            conn.execute(
                "UPDATE users SET subscription_expires_at = ? WHERE username = ?",
                (past, me["username"]),
            )
            conn.commit()
        # 触发 sync
        store.sync_subscription_status(me["id"])
        # 再充值 single
        r = client.post(
            "/api/billing/recharge",
            headers=_auth(token),
            json={"package": "single"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["user"]["tier"] == "paid"
        assert body["user"]["membership_status"] == "paid"
        assert isinstance(body["user"]["quota_remaining"], int)
        assert body["user"]["quota_remaining"] > 0
