"""v2.2 充值路由（mock 支付）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.schemas.billing import (
    BillingPackagesResponse,
    RechargeRequest,
    RechargeResponse,
)
from app.services.billing_service import BillingService

router = APIRouter(prefix="/billing", tags=["billing"])
billing_service = BillingService()


@router.get("/packages", response_model=BillingPackagesResponse)
def get_packages(current_user: dict = Depends(get_current_user)) -> dict:
    return billing_service.list_packages(current_user)


@router.post("/recharge", response_model=RechargeResponse)
def recharge(body: RechargeRequest, current_user: dict = Depends(get_current_user)) -> dict:
    return billing_service.recharge(current_user, body.package)


@router.get("/history")
def history(current_user: dict = Depends(get_current_user)) -> list[dict]:
    return billing_service.list_history(current_user)
