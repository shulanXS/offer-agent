"""v2.2/v2.5 充值服务（Stripe Checkout + 审计）。"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import settings
from app.core.errors import ErrorCode, raise_app_error
from app.db.store import Store
from app.services.payment_providers import (
    ProviderNotConfiguredError,
    get_provider,
)


def _packages_payload() -> list[dict[str, Any]]:
    return [
        {
            "id": "single",
            "title_zh": "标准包",
            "title_en": "Standard",
            "price_cents": settings.package_single_price_cents,
            "interviews": settings.package_single_interviews,
            "duration_days": None,
            "tagline_zh": "适合准备单场面试",
            "tagline_en": "For one focused interview prep",
        },
        {
            "id": "subscription",
            "title_zh": "月卡",
            "title_en": "Monthly Pass",
            "price_cents": settings.package_sub_price_cents,
            "interviews": None,
            "duration_days": settings.package_sub_duration_days,
            "tagline_zh": "无限次练习",
            "tagline_en": "Unlimited practice",
        },
    ]


def _now_plus(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _package_meta(package: str) -> tuple[int, int, str | None]:
    """(amount_cents, interviews_granted, subscription_expires_at)"""
    if package == "subscription":
        return (
            settings.package_sub_price_cents,
            0,
            _now_plus(settings.package_sub_duration_days),
        )
    return (
        settings.package_single_price_cents,
        settings.package_single_interviews,
        None,
    )


def _order_subject(package: str, is_en: bool) -> str:
    titles = {
        "single": ("Rally 标准包 · 5 次面试", "Rally Standard · 5 interviews"),
        "subscription": ("Rally 月卡 · 30 天无限次", "Rally Monthly Pass · 30 days unlimited"),
    }
    zh, en = titles[package]
    return en if is_en else zh


def _order_to_response(order: dict[str, Any]) -> dict[str, Any]:
    """把 DB 行格式化成对外的 PaymentOrder。"""
    metadata_raw = order.get("metadata_json") or "{}"
    try:
        metadata = json.loads(metadata_raw)
    except json.JSONDecodeError:
        metadata = {}
    return {
        "id": order["id"],
        "package": order["package"],
        "amount_cents": order["amount_cents"],
        "provider": order["provider"],
        "provider_order_id": order.get("provider_order_id"),
        "checkout_url": order.get("checkout_url"),
        "status": order.get("status", "pending"),
        "subject": order.get("subject"),
        "created_at": order.get("created_at"),
        "paid_at": order.get("paid_at"),
        "metadata": metadata,
    }


def _user_to_status(user: dict[str, Any]) -> dict[str, Any]:
    store = Store()
    return {
        "tier": user.get("tier", "free"),
        "quota_remaining": store.effective_quota_remaining(user),
        "membership_status": user.get("membership_status", "free"),
        "subscription_expires_at": user.get("subscription_expires_at"),
    }


class BillingService:
    def __init__(self) -> None:
        self.store = Store()

    # ---------------- 包列表 / 历史 ----------------
    def list_packages(self, user: dict) -> dict:
        synced = self.store.sync_subscription_status(int(user["id"])) or user
        return {
            "packages": _packages_payload(),
            "user": _user_to_status(synced),
        }

    def list_history(self, user: dict) -> list[dict]:
        return self.store.list_payments_for_user(int(user["id"]))

    def list_orders(self, user: dict) -> list[dict]:
        return [_order_to_response(o) for o in self.store.list_orders_for_user(int(user["id"]))]

    # ---------------- v2.5 真实下单 + 支付 ----------------
    def create_order(
        self,
        user: dict,
        package: str,
        *,
        provider_name: str | None = None,
        idempotency_key: str | None = None,
        is_en: bool = False,
    ) -> dict:
        if package not in {"single", "subscription"}:
            raise_app_error(400, ErrorCode.VALIDATION_ERROR, "未知套餐类型")
        user_id = int(user["id"])
        amount, _interviews, _expires = _package_meta(package)
        subject = _order_subject(package, is_en=is_en)

        # 幂等：先查现有订单
        if idempotency_key:
            existing = self.store._find_order_by_idempotency(user_id, idempotency_key)
            if existing:
                if existing["status"] == "paid":
                    user_after = self.store.get_user_by_id(user_id) or user
                    return {
                        "order": _order_to_response(existing),
                        "user": _user_to_status(user_after),
                    }
                # pending：复用同一个 provider_order_id + checkout_url，不再调 provider
                return {
                    "order": _order_to_response(existing),
                    "user": _user_to_status(self.store.get_user_by_id(user_id) or user),
                }

        try:
            provider = get_provider(provider_name)
        except ProviderNotConfiguredError as exc:
            raise_app_error(503, ErrorCode.PAYMENT_PROVIDER_UNCONFIGURED, str(exc))

        order_id = str(uuid.uuid4())
        try:
            checkout = provider.create_checkout(
                order_id=order_id,
                user_id=user_id,
                package=package,
                amount_cents=amount,
                subject=subject,
            )
        except ProviderNotConfiguredError as exc:
            raise_app_error(503, ErrorCode.PAYMENT_PROVIDER_UNCONFIGURED, str(exc))
        except Exception as exc:  # noqa: BLE001
            log_exception = exc
            raise_app_error(502, ErrorCode.INTERNAL_ERROR, f"支付通道创建订单失败: {log_exception}")

        order = self.store.create_order(
            order_id=order_id,
            user_id=user_id,
            package=package,
            amount_cents=amount,
            provider=provider.name,
            subject=subject,
            idempotency_key=idempotency_key,
            provider_order_id=checkout.provider_order_id,
            checkout_url=checkout.checkout_url,
            metadata=checkout.extra,
        )
        return {
            "order": _order_to_response(order),
            "user": _user_to_status(self.store.get_user_by_id(user_id) or user),
        }

    def get_order(self, user: dict, order_id: str) -> dict:
        order = self.store.get_order_for_user(order_id, int(user["id"]))
        if not order:
            raise_app_error(404, ErrorCode.PAYMENT_ORDER_NOT_FOUND, "订单不存在")
        user_after = self.store.get_user_by_id(int(user["id"])) or user
        return {
            "order": _order_to_response(order),
            "user": _user_to_status(user_after),
        }

    def handle_webhook(
        self,
        provider_name: str,
        payload: bytes,
        headers: dict[str, str],
    ) -> dict:
        """Provider 回调入口：解析 + 校验 + 入账。"""
        try:
            provider = get_provider(provider_name)
        except ProviderNotConfiguredError as exc:
            raise_app_error(503, ErrorCode.PAYMENT_PROVIDER_UNCONFIGURED, str(exc))

        try:
            result = provider.parse_webhook(payload=payload, headers=headers)
        except Exception as exc:  # noqa: BLE001
            raise_app_error(400, ErrorCode.VALIDATION_ERROR, f"webhook 解析失败: {exc}")
        if not result.paid:
            return {"ok": True, "status": "ignored", "reason": "not paid"}
        if not result.provider_order_id:
            raise_app_error(400, ErrorCode.VALIDATION_ERROR, "缺少 provider_order_id")
        order = self.store.find_order_by_provider_id(provider.name, result.provider_order_id)
        if not order:
            # 兜底：用 id 查
            order = self.store.get_order(result.provider_order_id)
        if not order:
            raise_app_error(404, ErrorCode.PAYMENT_ORDER_NOT_FOUND, "找不到对应订单")
        if order["status"] == "paid":
            return {"ok": True, "status": "already_paid", "order_id": order["id"]}
        # 金额校验
        if result.amount_cents and result.amount_cents != order["amount_cents"]:
            raise_app_error(400, ErrorCode.VALIDATION_ERROR, "回调金额不匹配")
        self._mark_order_paid(order)
        return {"ok": True, "status": "paid", "order_id": order["id"]}

    def _mark_order_paid(self, order: dict[str, Any]) -> dict:
        """将 pending 订单置为 paid，并入账（写 payments + apply_payment_to_user）。

        v2.4 幂等：`payments.idempotency_key=order:{id}`，重复触发会因 unique
        索引报错被吞掉。
        """
        from app.db.transaction import with_retry

        user_id = int(order["user_id"])
        package = order["package"]
        amount, interviews_granted, expires_at = _package_meta(package)

        def _do() -> dict[str, Any]:
            # 1) 标 paid
            self.store.update_order_status(
                order_id=order["id"],
                status="paid",
                paid_at=_now(),
            )
            # 2) 写审计 payments（关联原 order_id）
            try:
                self.store.record_payment(
                    payment_id=str(uuid.uuid4()),
                    user_id=user_id,
                    package=package,
                    amount_cents=amount,
                    interviews_granted=interviews_granted,
                    status="succeeded",
                    idempotency_key=f"order:{order['id']}",
                )
            except Exception as exc:  # noqa: BLE001
                if "uniq_payments_idem" not in str(exc):
                    raise
            # 3) 入账
            self.store.apply_payment_to_user(
                user_id=user_id,
                package=package,
                interviews_granted=interviews_granted,
                subscription_expires_at=expires_at,
            )
            user_after = self.store.get_user_by_id(user_id) or {}
            return {
                "order": _order_to_response(self.store.get_order(order["id"]) or order),
                "user": _user_to_status(user_after),
            }

        return with_retry(_do)
