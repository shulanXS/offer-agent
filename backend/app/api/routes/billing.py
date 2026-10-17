"""v2.2/v2.5 充值路由（真实 Stripe Checkout + webhook）。

- `GET /packages` 列套餐
- `POST /recharge` 已弃用但保留兼容：内部走真实下单（会失败如果未配置）
- `POST /orders` 创建真实订单，返回 Stripe Checkout `checkout_url`
- `GET /orders/{id}` 轮询订单状态
- `POST /webhook/{provider}` Stripe 回调入口
- `GET /history` 支付历史
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request

from app.api.deps import get_current_user
from app.core.locale import resolve_locale
from app.schemas.billing import (
    BillingPackagesResponse,
    CreateOrderRequest,
    CreateOrderResponse,
    OrderStatusResponse,
    RechargeRequest,
    RechargeResponse,
)
from app.services.billing_service import BillingService

log = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/billing", tags=["billing"])
billing_service = BillingService()


@router.get("/packages", response_model=BillingPackagesResponse)
def get_packages(current_user: dict = Depends(get_current_user)) -> dict:
    return billing_service.list_packages(current_user)


@router.post("/recharge", response_model=RechargeResponse)
def recharge(
    body: RechargeRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """兼容旧客户端：调真实下单拿 checkout_url（不直接入账）。"""
    locale = resolve_locale(request)
    is_en = locale.split("-")[0] == "en"
    result = billing_service.create_order(
        current_user,
        body.package,
        idempotency_key=body.idempotency_key,
        is_en=is_en,
    )
    # 旧接口期望 payment 字段，把 order 适配为 payment 形态
    return {
        "payment": {
            "id": result["order"]["id"],
            "provider": result["order"]["provider"],
            "checkout_url": result["order"]["checkout_url"],
            "status": result["order"]["status"],
        },
        "user": result["user"],
    }


@router.get("/history")
def history(current_user: dict = Depends(get_current_user)) -> list[dict]:
    return billing_service.list_history(current_user)


@router.post("/orders", response_model=CreateOrderResponse)
def create_order(
    body: CreateOrderRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> dict:
    locale = resolve_locale(request)
    is_en = locale.split("-")[0] == "en"
    return billing_service.create_order(
        current_user,
        body.package,
        provider_name=body.provider,
        idempotency_key=body.idempotency_key,
        is_en=is_en,
    )


@router.get("/orders", response_model=list[dict])
def list_orders(current_user: dict = Depends(get_current_user)) -> list[dict]:
    return billing_service.list_orders(current_user)


@router.get("/orders/{order_id}", response_model=OrderStatusResponse)
def get_order(
    order_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict:
    return billing_service.get_order(current_user, order_id)


@router.post("/webhook/{provider}")
async def webhook(
    provider: str,
    request: Request,
) -> dict:
    """Provider 回调入口（不要求登录）。"""
    payload = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    return billing_service.handle_webhook(provider, payload, headers)
