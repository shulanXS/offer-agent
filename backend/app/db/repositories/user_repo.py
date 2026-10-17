"""R1: User repository — 用户 CRUD、订阅同步、惰性 rehash。"""
from __future__ import annotations

import sqlite3
from typing import Any

from app.db.repositories.base import BaseRepository, _loads, _now


class UserRepository(BaseRepository):
    # ----- CRUD -----
    def create_user(self, username: str, password_hash: str, quota_remaining: int) -> dict[str, Any]:
        timestamp = _now()
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (username, password_hash, quota_remaining, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (username, password_hash, quota_remaining, timestamp, timestamp),
            )
            conn.commit()
            return self.get_user_by_id(cursor.lastrowid)

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    def get_user_with_synced_membership(self, user_id: int) -> dict[str, Any] | None:
        user = self.get_user_by_id(user_id)
        if not user:
            return None
        return self._sync_membership_in_memory(user)

    def update_user_password_hash(self, user_id: int, password_hash: str) -> None:
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                (password_hash, _now(), user_id),
            )
            conn.commit()

    # ----- Subscription -----
    def is_subscription_active(self, user: dict[str, Any]) -> bool:
        if user.get("membership_status") != "active_subscription":
            return False
        expires_at = user.get("subscription_expires_at")
        if not expires_at:
            return False
        try:
            ts = expires_at.replace("Z", "+00:00")
            from datetime import datetime, timezone
            return datetime.fromisoformat(ts) > datetime.now(timezone.utc)
        except (ValueError, TypeError):
            return False

    def effective_quota_remaining(self, user: dict[str, Any]) -> int | None:
        if self.is_subscription_active(user):
            return None
        return int(user.get("quota_remaining", 0))

    def _is_subscription_expired(self, user: dict[str, Any]) -> bool:
        if user.get("membership_status") == "active_subscription":
            expires_at = user.get("subscription_expires_at")
            if not expires_at:
                return True
            try:
                ts = expires_at.replace("Z", "+00:00")
                from datetime import datetime, timezone
                return datetime.fromisoformat(ts) <= datetime.now(timezone.utc)
            except (ValueError, TypeError):
                return True
        return False

    def _sync_membership_in_memory(self, user: dict[str, Any]) -> dict[str, Any]:
        if self._is_subscription_expired(user):
            user = dict(user)
            user["membership_status"] = "expired_subscription"
            user["tier"] = "free"
        return user

    def sync_subscription_status(self, user_id: int) -> dict[str, Any] | None:
        user = self.get_user_by_id(user_id)
        if not user:
            return None
        if not self._is_subscription_expired(user):
            return user
        from app.db.transaction import with_retry

        def _do() -> dict[str, Any] | None:
            with self.get_connection() as conn:
                conn.execute(
                    """
                    UPDATE users SET tier = 'free',
                                     membership_status = 'expired_subscription',
                                     updated_at = ?
                    WHERE id = ? AND (
                        membership_status = 'active_subscription'
                        OR tier = 'subscription'
                    )
                    """,
                    (_now(), user_id),
                )
                conn.commit()
            return self.get_user_by_id(user_id)

        return with_retry(_do)
