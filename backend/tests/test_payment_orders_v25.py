"""v2.5 真实支付订单（Stripe）测试。

覆盖：
- 通道未配置：STRIPE_SECRET_KEY 缺失时 create_order 返回 503
- 通道已配置：用 monkeypatch 替换 Stripe SDK，验证 create_order 走真实路径
- 订单幂等：同 key 重复创建返回同一订单
- 订单列表 / 详情 / 跨用户隔离
- 拉起 checkout：成功创建后 order 含 provider=stripe / checkout_url
- webhook (Stripe) 标记 paid + 触发入账；金额不匹配拒绝
- 二次创建时已 paid 的订单不会重复入账
- _mark_order_paid 幂等：同 order 重复触发不会双扣
"""
from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings


def _reg_and_login(client: TestClient, username: str | None = None, password: str = "pass1234"):
    name = username or f"buyer-{uuid.uuid4().hex[:8]}"
    r = client.post("/api/auth/register", json={"username": name, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def configured_stripe(monkeypatch: pytest.MonkeyPatch):
    """把 STRIPE_SECRET_KEY 设为测试值 + monkeypatch Stripe SDK，避免真实网络调用。"""
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_dummy", raising=False)
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_dummy", raising=False)
    monkeypatch.setattr(settings, "payment_provider", "stripe", raising=False)

    class FakeSession:
        def __init__(self, sid: str, url: str) -> None:
            self.id = sid
            self.url = url

    class FakeCheckout:
        @staticmethod
        def create(**kwargs):  # noqa: N802
            return FakeSession(
                sid="cs_test_" + uuid.uuid4().hex[:16],
                url=f"https://checkout.stripe.com/c/pay/{uuid.uuid4().hex}",
            )

    class FakeWebhook:
        @staticmethod
        def construct_event(payload, sig, secret):
            return json.loads(payload.decode("utf-8"))

    # 替换 import 路径下的 stripe
    import sys
    import types

    fake_module = types.ModuleType("stripe")
    fake_module.api_key = ""
    fake_module.checkout = types.SimpleNamespace(Session=FakeCheckout)
    fake_module.Webhook = FakeWebhook
    monkeypatch.setitem(sys.modules, "stripe", fake_module)
    yield


def test_create_order_no_stripe_key_returns_503(monkeypatch: pytest.MonkeyPatch):
    client = TestClient(app)
    token = _reg_and_login(client, username=f"nokey-{uuid.uuid4().hex[:8]}")
    headers = {"Authorization": f"Bearer {token}"}
    monkeypatch.setattr(settings, "stripe_secret_key", "", raising=False)
    r = client.post(
        "/api/billing/orders",
        json={"package": "single", "idempotency_key": "no-key-1"},
        headers=headers,
    )
    assert r.status_code == 503
    body = r.json()
    assert body["code"] == "PAYMENT_PROVIDER_UNCONFIGURED"


def test_create_order_with_stripe_returns_checkout_url(configured_stripe: None):
    client = TestClient(app)
    token = _reg_and_login(client, username=f"withkey-{uuid.uuid4().hex[:8]}")
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post(
        "/api/billing/orders",
        json={"package": "single", "idempotency_key": "with-key-1"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["order"]["package"] == "single"
    assert data["order"]["provider"] == "stripe"
    assert data["order"]["status"] == "pending"
    assert data["order"]["checkout_url"].startswith("https://checkout.stripe.com/")
    assert data["order"]["metadata"].get("session_id", "").startswith("cs_test_")


def test_create_order_idempotency(configured_stripe: None):
    client = TestClient(app)
    token = _reg_and_login(client, username=f"idem-{uuid.uuid4().hex[:8]}")
    headers = {"Authorization": f"Bearer {token}"}
    body = {"package": "single", "idempotency_key": "dup-1"}
    r1 = client.post("/api/billing/orders", json=body, headers=headers)
    r2 = client.post("/api/billing/orders", json=body, headers=headers)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["order"]["id"] == r2.json()["order"]["id"]


def test_list_orders(configured_stripe: None):
    client = TestClient(app)
    token = _reg_and_login(client, username=f"list-{uuid.uuid4().hex[:8]}")
    headers = {"Authorization": f"Bearer {token}"}
    client.post(
        "/api/billing/orders",
        json={"package": "single", "idempotency_key": "list-1"},
        headers=headers,
    )
    r = client.get("/api/billing/orders", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_get_order_other_user_404(configured_stripe: None):
    client = TestClient(app)
    a = _reg_and_login(client, username=f"a-{uuid.uuid4().hex[:8]}")
    b = _reg_and_login(client, username=f"b-{uuid.uuid4().hex[:8]}")
    a_h = {"Authorization": f"Bearer {a}"}
    b_h = {"Authorization": f"Bearer {b}"}
    created = client.post(
        "/api/billing/orders",
        json={"package": "single", "idempotency_key": "a-1"},
        headers=a_h,
    ).json()
    r = client.get(f"/api/billing/orders/{created['order']['id']}", headers=b_h)
    assert r.status_code == 404


def test_webhook_marks_order_paid_and_credits(configured_stripe: None):
    client = TestClient(app)
    token = _reg_and_login(client, username=f"wh-{uuid.uuid4().hex[:8]}")
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/api/billing/orders",
        json={"package": "single", "idempotency_key": "wh-1"},
        headers=headers,
    ).json()
    order_id = created["order"]["id"]
    provider_order_id = created["order"]["provider_order_id"]
    # 模拟 Stripe checkout.session.completed webhook
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": provider_order_id,
                "amount_total": created["order"]["amount_cents"],
                "metadata": {"order_id": order_id, "package": "single"},
            }
        },
    }
    r = client.post(
        "/api/billing/webhook/stripe",
        content=json.dumps(event).encode("utf-8"),
        headers={"Content-Type": "application/json", "Stripe-Signature": "t=1,v1=fake"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] in {"paid", "already_paid"}
    # 校验订单已是 paid
    r2 = client.get(f"/api/billing/orders/{order_id}", headers=headers)
    body = r2.json()
    assert body["order"]["status"] == "paid"
    assert body["user"]["tier"] == "paid"
    assert body["user"]["quota_remaining"] == 1 + settings.package_single_interviews


def test_webhook_amount_mismatch_rejected(configured_stripe: None):
    client = TestClient(app)
    token = _reg_and_login(client, username=f"mismatch-{uuid.uuid4().hex[:8]}")
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/api/billing/orders",
        json={"package": "single", "idempotency_key": "mm-1"},
        headers=headers,
    ).json()
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": created["order"]["provider_order_id"],
                "amount_total": 1,  # 篡改金额
                "metadata": {"order_id": created["order"]["id"]},
            }
        },
    }
    r = client.post(
        "/api/billing/webhook/stripe",
        content=json.dumps(event).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 400


def test_subscription_order_via_webhook_grants_unlimited(configured_stripe: None):
    client = TestClient(app)
    token = _reg_and_login(client, username=f"sub-{uuid.uuid4().hex[:8]}")
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/api/billing/orders",
        json={"package": "subscription", "idempotency_key": "sub-1"},
        headers=headers,
    ).json()
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": created["order"]["provider_order_id"],
                "amount_total": created["order"]["amount_cents"],
                "metadata": {"order_id": created["order"]["id"], "package": "subscription"},
            }
        },
    }
    client.post(
        "/api/billing/webhook/stripe",
        content=json.dumps(event).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    r = client.get(f"/api/billing/orders/{created['order']['id']}", headers=headers)
    body = r.json()
    assert body["order"]["status"] == "paid"
    assert body["user"]["membership_status"] == "active_subscription"
    assert body["user"]["tier"] == "subscription"
    assert body["user"]["quota_remaining"] is None
    assert body["user"]["subscription_expires_at"] is not None


def test_double_webhook_no_double_credit(configured_stripe: None):
    client = TestClient(app)
    token = _reg_and_login(client, username=f"dbl-{uuid.uuid4().hex[:8]}")
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/api/billing/orders",
        json={"package": "single", "idempotency_key": "dbl-1"},
        headers=headers,
    ).json()
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": created["order"]["provider_order_id"],
                "amount_total": created["order"]["amount_cents"],
                "metadata": {"order_id": created["order"]["id"]},
            }
        },
    }
    payload = json.dumps(event).encode("utf-8")
    r1 = client.post(
        "/api/billing/webhook/stripe",
        content=payload,
        headers={"Content-Type": "application/json"},
    )
    r2 = client.post(
        "/api/billing/webhook/stripe",
        content=payload,
        headers={"Content-Type": "application/json"},
    )
    assert r1.json()["status"] == "paid"
    assert r2.json()["status"] == "already_paid"
    # 拉最新 user，quota 应该只是 +5 一次
    r3 = client.get(f"/api/billing/orders/{created['order']['id']}", headers=headers)
    assert r3.json()["user"]["quota_remaining"] == 1 + settings.package_single_interviews
