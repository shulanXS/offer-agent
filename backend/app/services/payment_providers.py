"""v2.5 真实支付通道抽象。

设计目标：
- 通过环境变量启用，**不配置密钥时直接报错**，绝不退化为本地 mock
- 实现统一接口的 `PaymentProvider`，便于后续扩展其它通道
- 上层（billing_service）只跟接口打交道
"""
from __future__ import annotations

import abc
import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

from app.core.config import settings

log = logging.getLogger(__name__)


@dataclass
class CheckoutResult:
    """Provider 端创建订单后的结果。"""

    provider_order_id: str
    checkout_url: str
    # 透传给前端的附加信息（如支付意图 ID / client_secret）
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class WebhookResult:
    """Webhook 解析结果。"""

    provider_order_id: str
    paid: bool
    # 透传原始金额，billing_service 二次校验
    amount_cents: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class PaymentProvider(abc.ABC):
    """支付通道统一接口。"""

    name: str = "abstract"

    @abc.abstractmethod
    def create_checkout(
        self,
        *,
        order_id: str,
        user_id: int,
        package: str,
        amount_cents: int,
        subject: str,
    ) -> CheckoutResult: ...

    @abc.abstractmethod
    def parse_webhook(
        self,
        *,
        payload: bytes,
        headers: dict[str, str],
    ) -> WebhookResult: ...


class ProviderNotConfiguredError(RuntimeError):
    """通道未配置：缺关键环境变量时抛出。"""


# ---------------------------------------------------------------------------
# Stripe（仅此一个通道）
# ---------------------------------------------------------------------------
class StripeProvider(PaymentProvider):
    """Stripe Checkout 通道。

    依赖：环境变量 `STRIPE_SECRET_KEY`、`STRIPE_WEBHOOK_SECRET`。
    使用 `stripe` SDK（如未安装则抛出明确错误，提示用户安装）。
    """

    name = "stripe"

    def __init__(self) -> None:
        self._sdk_error: str | None = None
        if not settings.stripe_secret_key:
            raise ProviderNotConfiguredError(
                "STRIPE_SECRET_KEY 未配置：请在 backend/.env 设置后再启动"
            )
        try:
            import stripe  # type: ignore[import-not-found]

            self._stripe = stripe
            self._stripe.api_key = settings.stripe_secret_key
        except Exception as exc:  # noqa: BLE001
            self._stripe = None  # type: ignore[assignment]
            self._sdk_error = f"stripe sdk not available: {exc}"

    def create_checkout(
        self,
        *,
        order_id: str,
        user_id: int,
        package: str,
        amount_cents: int,
        subject: str,
    ) -> CheckoutResult:
        if self._stripe is None:
            raise ProviderNotConfiguredError(self._sdk_error or "stripe sdk not initialised")
        session = self._stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": settings.stripe_currency,
                        "unit_amount": amount_cents,
                        "product_data": {"name": subject},
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=f"{settings.frontend_base_url}/billing/return?order_id={order_id}&status=success",
            cancel_url=f"{settings.frontend_base_url}/billing/return?order_id={order_id}&status=cancel",
            metadata={"order_id": order_id, "user_id": str(user_id), "package": package},
        )
        return CheckoutResult(
            provider_order_id=session.id,
            checkout_url=session.url or "",
            extra={"session_id": session.id, "publishable_key": settings.stripe_publishable_key},
        )

    def parse_webhook(
        self,
        *,
        payload: bytes,
        headers: dict[str, str],
    ) -> WebhookResult:
        if self._stripe is None:
            raise ProviderNotConfiguredError(self._sdk_error or "stripe sdk not initialised")
        if not settings.stripe_webhook_secret:
            raise ProviderNotConfiguredError("STRIPE_WEBHOOK_SECRET 未配置")
        sig = headers.get("stripe-signature", "")
        event = self._stripe.Webhook.construct_event(
            payload, sig, settings.stripe_webhook_secret
        )
        if event["type"] != "checkout.session.completed":
            return WebhookResult(provider_order_id="", paid=False, raw={"type": event["type"]})
        session = event["data"]["object"]
        amount_total = session.get("amount_total")
        return WebhookResult(
            provider_order_id=str(session.get("id", "")),
            paid=True,
            amount_cents=int(amount_total) if amount_total else None,
            raw={"metadata": session.get("metadata", {}), "amount_total": amount_total},
        )


# ---------------------------------------------------------------------------
# 工厂
# ---------------------------------------------------------------------------
_PROVIDERS: dict[str, type[PaymentProvider]] = {
    "stripe": StripeProvider,
}


def get_provider(name: str | None = None) -> PaymentProvider:
    """按配置或入参取一个 provider 实例。

    通道未配置密钥时**直接抛 ProviderNotConfiguredError**，由上层转换为 503。
    """
    name = (name or settings.payment_provider or "stripe").lower()
    if name not in _PROVIDERS:
        raise ProviderNotConfiguredError(f"不支持的支付通道: {name}")
    return _PROVIDERS[name]()  # type: ignore[abstract]
