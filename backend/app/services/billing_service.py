"""v2.2 充值服务（mock 支付 + 审计）。"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import settings
from app.core.errors import ErrorCode, raise_app_error
from app.db.store import Store


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


class BillingService:
    def __init__(self) -> None:
        self.store = Store()

    def list_packages(self, user: dict) -> dict:
        return {
            "packages": _packages_payload(),
            "user": {
                "tier": user.get("tier", "free"),
                "quota_remaining": self.store.effective_quota_remaining(user),
                "subscription_expires_at": user.get("subscription_expires_at"),
            },
        }

    def recharge(self, user: dict, package: str) -> dict:
        if package not in {"single", "subscription"}:
            raise_app_error(400, ErrorCode.VALIDATION_ERROR, "未知套餐类型")
        user_id = int(user["id"])

        if package == "subscription":
            amount = settings.package_sub_price_cents
            interviews_granted = 0
            expires_at = _now_plus(settings.package_sub_duration_days)
        else:  # single
            amount = settings.package_single_price_cents
            interviews_granted = settings.package_single_interviews
            expires_at = None

        payment = self.store.record_payment(
            payment_id=str(uuid.uuid4()),
            user_id=user_id,
            package=package,
            amount_cents=amount,
            interviews_granted=interviews_granted,
            status="succeeded",
        )
        user_after = self.store.apply_payment_to_user(
            user_id=user_id,
            package=package,
            interviews_granted=interviews_granted,
            subscription_expires_at=expires_at,
        )

        if not user_after:
            raise_app_error(404, ErrorCode.USER_NOT_FOUND, "用户不存在")

        return {
            "payment": payment,
            "user": {
                "tier": user_after.get("tier", "free"),
                "quota_remaining": self.store.effective_quota_remaining(user_after),
                "subscription_expires_at": user_after.get("subscription_expires_at"),
            },
        }

    def list_history(self, user: dict) -> list[dict]:
        return self.store.list_payments_for_user(int(user["id"]))
