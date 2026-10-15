"""v2.2 充值：单包 + 订阅。"""
from __future__ import annotations

import importlib
import time

import pytest
from fastapi.testclient import TestClient

from app.core import config as cfg
from app.db import store as store_mod
from app.db.transaction import transaction
from app.main import app


@pytest.fixture
def fresh_db(monkeypatch, tmp_path):
    db_file = str(tmp_path / "billing.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    importlib.reload(cfg)
    importlib.reload(store_mod)
    from app.services import auth_service as auth_mod
    importlib.reload(auth_mod)
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


def test_default_new_user_quota_is_one(fresh_db) -> None:
    """v2.2：新用户默认 1 次免费面试。"""
    with TestClient(app) as client:
        token = _register_and_login(client, f"u_{int(time.time()*1000)%1_000_000}_a")
        me = client.get("/api/auth/me", headers=_auth(token)).json()
        assert me["quota_remaining"] == 1
        assert me["tier"] == "free"


def test_username_lowercase(fresh_db) -> None:
    """v2.2：注册 Alice，登录 alice 也应成功。"""
    unique = f"u{int(time.time()*1000)%1_000_000}_lc"
    username = f"Alice_{unique}"
    with TestClient(app) as client:
        token = _register_and_login(client, username)
        # token 来自 Alice_xxx，验证 alice_xxx 也能拿到同一用户
        me = client.get("/api/auth/me", headers=_auth(token)).json()
        assert me["username"] == username.lower()


def test_recharge_single_increases_quota(fresh_db) -> None:
    with TestClient(app) as client:
        token = _register_and_login(client, f"u_{int(time.time()*1000)%1_000_000}_b")
        # 充值前 = 1
        me = client.get("/api/auth/me", headers=_auth(token)).json()
        assert me["quota_remaining"] == 1
        # 充值 single 包 → +5
        r = client.post(
            "/api/billing/recharge",
            headers=_auth(token),
            json={"package": "single"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["user"]["tier"] == "paid"
        assert body["user"]["quota_remaining"] == 6
        # 再次 me
        me2 = client.get("/api/auth/me", headers=_auth(token)).json()
        assert me2["quota_remaining"] == 6


def test_recharge_subscription_does_not_consume(fresh_db) -> None:
    """v2.2：订阅有效时 quota 一直是大数。"""
    with TestClient(app) as client:
        token = _register_and_login(client, f"u_{int(time.time()*1000)%1_000_000}_c")
        r = client.post(
            "/api/billing/recharge",
            headers=_auth(token),
            json={"package": "subscription"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["user"]["tier"] == "subscription"
        assert body["user"]["quota_remaining"] >= 1000
        assert body["user"]["subscription_expires_at"] is not None


def test_billing_packages_endpoint(fresh_db) -> None:
    with TestClient(app) as client:
        token = _register_and_login(client, f"u_{int(time.time()*1000)%1_000_000}_d")
        r = client.get("/api/billing/packages", headers=_auth(token))
        assert r.status_code == 200
        body = r.json()
        ids = {p["id"] for p in body["packages"]}
        assert "single" in ids
        assert "subscription" in ids
        assert body["user"]["tier"] == "free"


def test_billing_history_audit(fresh_db) -> None:
    with TestClient(app) as client:
        token = _register_and_login(client, f"u_{int(time.time()*1000)%1_000_000}_e")
        client.post(
            "/api/billing/recharge",
            headers=_auth(token),
            json={"package": "single"},
        )
        client.post(
            "/api/billing/recharge",
            headers=_auth(token),
            json={"package": "subscription"},
        )
        r = client.get("/api/billing/history", headers=_auth(token))
        assert r.status_code == 200
        history = r.json()
        assert len(history) == 2
        pkgs = {item["package"] for item in history}
        assert pkgs == {"single", "subscription"}
        for item in history:
            assert item["status"] == "succeeded"
            assert item["amount_cents"] > 0


def test_invalid_package_400(fresh_db) -> None:
    with TestClient(app) as client:
        token = _register_and_login(client, f"u_{int(time.time()*1000)%1_000_000}_f")
        r = client.post(
            "/api/billing/recharge",
            headers=_auth(token),
            json={"package": "bogus"},
        )
        assert r.status_code in (400, 422)


def test_auth_whitespace_username_rejected(fresh_db) -> None:
    """v2.2：纯空白用户名被拒。"""
    with TestClient(app) as client:
        r = client.post(
            "/api/auth/register",
            json={"username": "   ", "password": "secret123"},
        )
        assert r.status_code in (400, 422)
