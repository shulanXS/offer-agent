"""v2.2/v2.3/v2.5 充值相关 schema。"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class BillingUserStatus(BaseModel):
    tier: str
    # v2.3: 订阅有效时为 None（=无限），其他为真实剩余
    quota_remaining: int | None = None
    membership_status: str = "free"
    subscription_expires_at: str | None = None


class BillingPackage(BaseModel):
    id: Literal["single", "subscription"]
    title_zh: str
    title_en: str
    price_cents: int
    interviews: int | None = None
    duration_days: int | None = None
    tagline_zh: str
    tagline_en: str


class BillingPackagesResponse(BaseModel):
    packages: list[BillingPackage]
    user: BillingUserStatus


class RechargeRequest(BaseModel):
    package: Literal["single", "subscription"]
    # 幂等键（v2.4）：同 key 在 5 分钟内只生效一次，防双扣
    idempotency_key: str | None = Field(default=None, max_length=64)


class RechargeResponse(BaseModel):
    payment: dict
    user: BillingUserStatus


# ---------------------------------------------------------------------------
# v2.5：真实支付订单
# ---------------------------------------------------------------------------
OrderStatus = Literal["pending", "paid", "failed", "cancelled"]


class CreateOrderRequest(BaseModel):
    package: Literal["single", "subscription"]
    # 客户端生成的幂等键（同 key 同一用户只创建一笔订单）
    idempotency_key: str | None = Field(default=None, max_length=64)
    # provider 名称（缺省走 settings.payment_provider）
    provider: str | None = Field(default=None, max_length=32)


class PaymentOrder(BaseModel):
    id: str
    package: str
    amount_cents: int
    provider: str
    provider_order_id: str | None = None
    checkout_url: str | None = None
    status: OrderStatus
    subject: str | None = None
    created_at: str
    paid_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateOrderResponse(BaseModel):
    order: PaymentOrder
    user: BillingUserStatus


class OrderStatusResponse(BaseModel):
    order: PaymentOrder
    user: BillingUserStatus
