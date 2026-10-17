"""v2.5 充值：单包 + 订阅（通过真实 Stripe 流程 + webhook）。

历史 v2.2 测试依赖「mock 即时入账」接口，v2.5 改为真实 Stripe 后改为：
  POST /api/billing/orders → POST /api/billing/webhook/stripe
"""
from __future__ import annotations

import importlib
import json
import sys
import time
import types
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core import config as cfg
from app.db import store as store_mod
from app.main import app
from app.services.billing_service import BillingService


class _FreshDb:
    def __init__(self, db_file, app):
        self.db_file = db_file
        self.app = app


@pytest.fixture
def fresh_db(monkeypatch, tmp_path):
    """v2.5 简化版：不 reload 任何模块，只在已加载的 settings 上注入测试值。
    BillingService 通过 `from app.core.config import settings` 拿到的是同一个对象引用，
    立即能看到注入的属性。store 通过 `importlib.reload` 重建以使用临时 DB。"""
    db_file = str(tmp_path / "billing.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    importlib.reload(store_mod)
    from app.services import auth_service as auth_mod
    importlib.reload(auth_mod)
    # 直接给已加载的 settings 注入 Stripe 测试密钥
    monkeypatch.setattr(cfg.settings, "stripe_secret_key", "sk_test_dummy", raising=False)
    monkeypatch.setattr(cfg.settings, "stripe_webhook_secret", "whsec_dummy", raising=False)
    monkeypatch.setattr(cfg.settings, "payment_provider", "stripe", raising=False)
    store_mod.init_db()
    yield _FreshDb(db_file=db_file, app=app)


class _FakeSession:
    def __init__(self) -> None:
        self.id = "cs_test_" + uuid.uuid4().hex[:16]
        self.url = f"https://checkout.stripe.com/c/pay/{uuid.uuid4().hex}"


@pytest.fixture
def stripe_ready(monkeypatch):
    """monkeypatch Stripe SDK 避免真实网络调用。fresh_db 已设置 STRIPE_SECRET_KEY。"""
    fake = types.ModuleType("stripe")
    fake.api_key = ""

    def _create(**kwargs):
        return _FakeSession()

    fake.checkout = types.SimpleNamespace(Session=types.SimpleNamespace(create=_create))
    fake.Webhook = types.SimpleNamespace(
        construct_event=lambda payload, sig, secret: json.loads(payload.decode("utf-8"))
    )
    monkeypatch.setitem(sys.modules, "stripe", fake)
    yield


def _register_and_login(client: TestClient, username: str, password: str = "secret123") -> str:
    response = client.post(
        "/api/auth/register",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _fulfill(client: TestClient, token: str, order_id: str, provider_order_id: str, amount: int) -> None:
    """模拟 Stripe checkout.session.completed webhook 入账。"""
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": provider_order_id,
                "amount_total": amount,
                "metadata": {"order_id": order_id, "package": "single"},
            }
        },
    }
    r = client.post(
        "/api/billing/webhook/stripe",
        content=json.dumps(event).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 200, r.text


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
        me = client.get("/api/auth/me", headers=_auth(token)).json()
        assert me["username"] == username.lower()


def test_recharge_single_increases_quota(fresh_db, stripe_ready) -> None:
    with TestClient(app) as client:
        token = _register_and_login(client, f"u_{int(time.time()*1000)%1_000_000}_b")
        me = client.get("/api/auth/me", headers=_auth(token)).json()
        assert me["quota_remaining"] == 1
        # 下单
        r = client.post(
            "/api/billing/orders",
            headers=_auth(token),
            json={"package": "single", "idempotency_key": f"k-{uuid.uuid4().hex[:8]}"},
        )
        assert r.status_code == 200, r.text
        order = r.json()["order"]
        # webhook 入账
        _fulfill(client, token, order["id"], order["provider_order_id"], order["amount_cents"])
        # 校验
        me2 = client.get("/api/auth/me", headers=_auth(token)).json()
        assert me2["tier"] == "paid"
        assert me2["quota_remaining"] == 6


def test_recharge_subscription_does_not_consume(fresh_db, stripe_ready) -> None:
    """v2.2/v2.3：订阅有效时 quota 为 None（=无限）。"""
    with TestClient(app) as client:
        token = _register_and_login(client, f"u_{int(time.time()*1000)%1_000_000}_c")
        r = client.post(
            "/api/billing/orders",
            headers=_auth(token),
            json={"package": "subscription", "idempotency_key": f"k-{uuid.uuid4().hex[:8]}"},
        )
        assert r.status_code == 200, r.text
        order = r.json()["order"]
        _fulfill(client, token, order["id"], order["provider_order_id"], order["amount_cents"])
        me = client.get("/api/auth/me", headers=_auth(token)).json()
        assert me["tier"] == "subscription"
        assert me["quota_remaining"] is None
        assert me["subscription_expires_at"] is not None
        assert me["membership_status"] == "active_subscription"


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


def test_billing_history_audit(fresh_db, stripe_ready) -> None:
    with TestClient(app) as client:
        token = _register_and_login(client, f"u_{int(time.time()*1000)%1_000_000}_e")
        for pkg in ("single", "subscription"):
            r = client.post(
                "/api/billing/orders",
                headers=_auth(token),
                json={"package": pkg, "idempotency_key": f"k-{uuid.uuid4().hex[:8]}"},
            )
            assert r.status_code == 200
            order = r.json()["order"]
            _fulfill(client, token, order["id"], order["provider_order_id"], order["amount_cents"])
        history = client.get("/api/billing/history", headers=_auth(token)).json()
        assert len(history) == 2
        pkgs = {item["package"] for item in history}
        assert pkgs == {"single", "subscription"}
        for item in history:
            assert item["status"] == "succeeded"
            assert item["amount_cents"] > 0


def test_invalid_package_400(fresh_db, stripe_ready) -> None:
    with TestClient(app) as client:
        token = _register_and_login(client, f"u_{int(time.time()*1000)%1_000_000}_f")
        r = client.post(
            "/api/billing/orders",
            headers=_auth(token),
            json={"package": "bogus", "idempotency_key": "x"},
        )
        assert r.status_code in (400, 422)


def test_recharge_idempotency_key(fresh_db, stripe_ready) -> None:
    """v2.5：同 idempotency_key 重复下单只产生一笔订单 + 一次入账。"""
    with TestClient(app) as client:
        token = _register_and_login(client, f"u_{int(time.time()*1000)%1_000_000}_idem")
        key = f"test-key-{uuid.uuid4().hex[:8]}"
        r1 = client.post(
            "/api/billing/orders",
            headers=_auth(token),
            json={"package": "single", "idempotency_key": key},
        )
        assert r1.status_code == 200, r1.text
        order = r1.json()["order"]
        _fulfill(client, token, order["id"], order["provider_order_id"], order["amount_cents"])
        quota1 = client.get("/api/auth/me", headers=_auth(token)).json()["quota_remaining"]

        r2 = client.post(
            "/api/billing/orders",
            headers=_auth(token),
            json={"package": "single", "idempotency_key": key},
        )
        assert r2.status_code == 200, r2.text
        # 同 key → 同一订单
        assert r2.json()["order"]["id"] == order["id"]
        # quota 不变
        quota2 = client.get("/api/auth/me", headers=_auth(token)).json()["quota_remaining"]
        assert quota1 == quota2
        # payments 只有 1 笔
        history = client.get("/api/billing/history", headers=_auth(token)).json()
        assert len(history) == 1


def test_auth_whitespace_username_rejected(fresh_db) -> None:
    """v2.2：纯空白用户名被拒。"""
    with TestClient(app) as client:
        r = client.post(
            "/api/auth/register",
            json={"username": "   ", "password": "secret123"},
        )
        assert r.status_code in (400, 422)
