"""v2.2 充值相关 schema。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class BillingUserStatus(BaseModel):
    tier: str
    quota_remaining: int
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


class RechargeResponse(BaseModel):
    payment: dict
    user: BillingUserStatus
