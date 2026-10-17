"""v2.3 订阅状态同步对外 facade。

将订阅状态机收敛为单一权威源（见改进方案 v2.3 §3.1）。
真正的同步逻辑已合并到 `app.db.store.Store.sync_subscription_status` / `get_user_with_synced_membership`，
此处仅做语义化 re-export，方便 service 层在不改 import 路径的情况下调用。
"""
from __future__ import annotations

from app.db.store import Store

__all__ = ["Store", "sync_subscription_status", "get_user_with_synced_membership"]


def sync_subscription_status(user_id: int) -> dict | None:
    return Store().sync_subscription_status(user_id)


def get_user_with_synced_membership(user_id: int) -> dict | None:
    return Store().get_user_with_synced_membership(user_id)
