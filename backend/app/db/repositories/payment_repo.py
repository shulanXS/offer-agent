"""R1+R3: Payment repository — payments + payment_orders（含事务化 apply_payment）。"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.db.repositories.base import BaseRepository, _now
from app.db.repositories.user_repo import UserRepository


class PaymentRepository(BaseRepository):
    # ----- payments -----
    def record_payment(
        self,
        *,
        payment_id: str,
        user_id: int,
        package: str,
        amount_cents: int,
        interviews_granted: int,
        status: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """v2.4：支持 idempotency_key，同 (user, key) 重复提交返回首次记录。"""
        timestamp = _now()
        with self.get_connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO payments (
                        id, user_id, package, amount_cents, interviews_granted,
                        status, created_at, completed_at, idempotency_key
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payment_id,
                        user_id,
                        package,
                        amount_cents,
                        interviews_granted,
                        status,
                        timestamp,
                        timestamp if status == "succeeded" else None,
                        idempotency_key,
                    ),
                )
                conn.commit()
            except Exception as exc:  # noqa: BLE001
                if idempotency_key and "uniq_payments_idem" in str(exc):
                    existing = self._find_payment_by_idempotency(user_id, idempotency_key)
                    if existing:
                        return existing
                raise
        return self.get_payment(payment_id)

    def _find_payment_by_idempotency(self, user_id: int, key: str) -> dict[str, Any] | None:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM payments WHERE user_id = ? AND idempotency_key = ?",
                (user_id, key),
            ).fetchone()
        return dict(row) if row else None

    def get_payment(self, payment_id: str) -> dict[str, Any] | None:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()
        return dict(row) if row else None

    def list_payments_for_user(self, user_id: int) -> list[dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM payments WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    # ----- 事务内版本：R3 -----
    def update_order_status_in_conn(
        self,
        conn: sqlite3.Connection,
        *,
        order_id: str,
        status: str,
        paid_at: str | None = None,
    ) -> None:
        """R3：事务内更新订单状态（无 commit）。"""
        conn.execute(
            "UPDATE payment_orders SET status = ?, paid_at = COALESCE(?, paid_at) WHERE id = ?",
            (status, paid_at, order_id),
        )

    def record_payment_in_conn(
        self,
        conn: sqlite3.Connection,
        *,
        payment_id: str,
        user_id: int,
        package: str,
        amount_cents: int,
        interviews_granted: int,
        status: str,
        idempotency_key: str | None = None,
    ) -> bool:
        """R3：事务内写 payments。返回 True 表示新写入，False 表示幂等命中。
        
        重复 (user, idempotency_key) 不抛异常，直接返回 False。
        """
        try:
            conn.execute(
                """
                INSERT INTO payments (
                    id, user_id, package, amount_cents, interviews_granted,
                    status, created_at, completed_at, idempotency_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payment_id,
                    user_id,
                    package,
                    amount_cents,
                    interviews_granted,
                    status,
                    _now(),
                    _now() if status == "succeeded" else None,
                    idempotency_key,
                ),
            )
            return True
        except Exception as exc:  # noqa: BLE001
            if idempotency_key and "uniq_payments_idem" in str(exc):
                return False
            raise

    def apply_payment_in_conn(
        self,
        conn: sqlite3.Connection,
        *,
        user_id: int,
        package: str,
        interviews_granted: int,
        subscription_expires_at: str | None,
    ) -> None:
        """R3：事务内更新 user tier / quota / subscription_expires_at / membership_status。"""
        row = conn.execute(
            "SELECT membership_status FROM users WHERE id = ?", (user_id,),
        ).fetchone()
        if not row:
            return
        current_status = str(row["membership_status"] or "free")
        if package == "subscription":
            conn.execute(
                """
                UPDATE users SET tier = 'subscription',
                                 membership_status = 'active_subscription',
                                 subscription_expires_at = ?,
                                 updated_at = ?
                WHERE id = ?
                """,
                (subscription_expires_at, _now(), user_id),
            )
        elif current_status == "active_subscription":
            conn.execute(
                """
                UPDATE users SET quota_remaining = quota_remaining + ?,
                                 updated_at = ?
                WHERE id = ?
                """,
                (interviews_granted, _now(), user_id),
            )
        else:
            conn.execute(
                """
                UPDATE users SET tier = 'paid',
                                 membership_status = 'paid',
                                 quota_remaining = quota_remaining + ?,
                                 updated_at = ?
                WHERE id = ?
                """,
                (interviews_granted, _now(), user_id),
            )

    # ----- apply payment (R3: transaction wrap) -----
    def apply_payment_to_user(
        self,
        *,
        user_id: int,
        package: str,
        interviews_granted: int,
        subscription_expires_at: str | None,
    ) -> dict[str, Any] | None:
        """R3: 单事务更新 user tier / quota / subscription_expires_at / membership_status。"""
        from app.db.transaction import with_retry

        def _do() -> dict[str, Any] | None:
            with self.get_connection() as conn:
                row = conn.execute(
                    "SELECT id, membership_status FROM users WHERE id = ?", (user_id,),
                ).fetchone()
                if not row:
                    return None
                current_status = str(row["membership_status"] or "free")
                if package == "subscription":
                    conn.execute(
                        """
                        UPDATE users SET tier = 'subscription',
                                         membership_status = 'active_subscription',
                                         subscription_expires_at = ?,
                                         updated_at = ?
                        WHERE id = ?
                        """,
                        (subscription_expires_at, _now(), user_id),
                    )
                else:
                    if current_status == "active_subscription":
                        conn.execute(
                            """
                            UPDATE users SET quota_remaining = quota_remaining + ?,
                                             updated_at = ?
                            WHERE id = ?
                            """,
                            (interviews_granted, _now(), user_id),
                        )
                    else:
                        conn.execute(
                            """
                            UPDATE users SET tier = 'paid',
                                             membership_status = 'paid',
                                             quota_remaining = quota_remaining + ?,
                                             updated_at = ?
                            WHERE id = ?
                            """,
                            (interviews_granted, _now(), user_id),
                        )
                conn.commit()
            return UserRepository().get_user_by_id(user_id)

        return with_retry(_do)

    # ----- payment_orders -----
    def create_order(
        self,
        *,
        order_id: str,
        user_id: int,
        package: str,
        amount_cents: int,
        provider: str,
        subject: str,
        idempotency_key: str | None = None,
        provider_order_id: str | None = None,
        checkout_url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """创建支付订单。带 idempotency_key 重复时返回旧单。"""
        timestamp = _now()
        with self.get_connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO payment_orders (
                        id, user_id, package, amount_cents, provider,
                        provider_order_id, checkout_url, status,
                        idempotency_key, subject, created_at, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)
                    """,
                    (
                        order_id,
                        user_id,
                        package,
                        amount_cents,
                        provider,
                        provider_order_id or order_id,
                        checkout_url,
                        idempotency_key,
                        subject,
                        timestamp,
                        json.dumps(metadata or {}, ensure_ascii=False),
                    ),
                )
                conn.commit()
            except Exception as exc:  # noqa: BLE001
                if idempotency_key and "uniq_payment_orders_idem" in str(exc):
                    existing = self._find_order_by_idempotency(user_id, idempotency_key)
                    if existing:
                        return existing
                raise
        return self.get_order(order_id) or {}

    def _find_order_by_idempotency(self, user_id: int, key: str) -> dict[str, Any] | None:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM payment_orders WHERE user_id = ? AND idempotency_key = ?",
                (user_id, key),
            ).fetchone()
        return dict(row) if row else None

    def get_order(self, order_id: str) -> dict[str, Any] | None:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM payment_orders WHERE id = ?", (order_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_order_for_user(self, order_id: str, user_id: int) -> dict[str, Any] | None:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM payment_orders WHERE id = ? AND user_id = ?",
                (order_id, user_id),
            ).fetchone()
        return dict(row) if row else None

    def find_order_by_provider_id(
        self, provider: str, provider_order_id: str
    ) -> dict[str, Any] | None:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM payment_orders WHERE provider = ? AND provider_order_id = ?",
                (provider, provider_order_id),
            ).fetchone()
        return dict(row) if row else None

    def update_order_status(
        self,
        *,
        order_id: str,
        status: str,
        paid_at: str | None = None,
    ) -> dict[str, Any] | None:
        """更新订单状态。允许 pending -> paid / failed / cancelled。"""
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE payment_orders SET status = ?, paid_at = COALESCE(?, paid_at) WHERE id = ?",
                (status, paid_at, order_id),
            )
            conn.commit()
        return self.get_order(order_id)

    def list_orders_for_user(self, user_id: int) -> list[dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM payment_orders WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]
