"""R1+R3: Quota repository — quota 增减 + audit（事务化）。"""
from __future__ import annotations

import sqlite3
from typing import Any

from app.db.repositories.base import BaseRepository, _now
from app.db.repositories.user_repo import UserRepository


class QuotaRepository(BaseRepository):
    def decrement_quota(
        self,
        user_id: int,
        *,
        session_id: str | None = None,
        reason: str = "interview_activate",
    ) -> dict[str, Any] | None:
        """3.4：原子扣减 + 写 audit。保留 with_retry 包装以容忍 'database is locked'。"""
        from app.db.transaction import with_retry

        def _do() -> dict[str, Any] | None:
            with self.get_connection() as conn:
                row = conn.execute(
                    "SELECT quota_remaining FROM users WHERE id = ?", (user_id,),
                ).fetchone()
                if not row or row["quota_remaining"] <= 0:
                    return None
                conn.execute(
                    "UPDATE users SET quota_remaining = quota_remaining - 1, updated_at = ? WHERE id = ?",
                    (_now(), user_id),
                )
                conn.execute(
                    """
                    INSERT INTO quota_audit (user_id, delta, reason, session_id, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user_id, -1, reason, session_id, _now()),
                )
                conn.commit()
                return UserRepository().get_user_by_id(user_id)

        return with_retry(_do)

    def compensate_quota(
        self,
        user_id: int,
        *,
        session_id: str | None = None,
        reason: str = "interview_activate_rollback",
    ) -> dict[str, Any] | None:
        """3.4：补偿 +1。事务外版本。"""
        from app.db.transaction import with_retry

        def _do() -> dict[str, Any] | None:
            with self.get_connection() as conn:
                row = conn.execute(
                    "SELECT quota_remaining FROM users WHERE id = ?", (user_id,),
                ).fetchone()
                if not row:
                    return None
                conn.execute(
                    "UPDATE users SET quota_remaining = quota_remaining + 1, updated_at = ? WHERE id = ?",
                    (_now(), user_id),
                )
                conn.execute(
                    """
                    INSERT INTO quota_audit (user_id, delta, reason, session_id, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user_id, +1, reason, session_id, _now()),
                )
                conn.commit()
                return UserRepository().get_user_by_id(user_id)

        return with_retry(_do)

    def audit_outcome_for_session(
        self, session_id: str, *, reason: str = "auto_compensation"
    ) -> dict[str, Any] | None:
        """3.4：发现'已 decrement 但无 outcome'孤儿记录，触发回滚额度。"""
        from app.db.transaction import with_retry

        def _do() -> dict[str, Any] | None:
            with self.get_connection() as conn:
                row = conn.execute(
                    """
                    SELECT user_id FROM learning_session_outcomes
                    WHERE session_id = ? AND deleted_at IS NULL
                    """,
                    (session_id,),
                ).fetchone()
                if row is not None:
                    return None
                audit = conn.execute(
                    """
                    SELECT user_id FROM quota_audit
                    WHERE session_id = ? AND delta = -1
                    ORDER BY id DESC LIMIT 1
                    """,
                    (session_id,),
                ).fetchone()
                if not audit:
                    return None
                user_id = int(audit["user_id"])
                conn.execute(
                    "UPDATE users SET quota_remaining = quota_remaining + 1, updated_at = ? WHERE id = ?",
                    (_now(), user_id),
                )
                conn.execute(
                    """
                    INSERT INTO quota_audit (user_id, delta, reason, session_id, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user_id, +1, reason, session_id, _now()),
                )
                conn.commit()
                return UserRepository().get_user_by_id(user_id)

        return with_retry(_do)

    # ----- 事务内版本：R3 -----
    def decrement_quota_in_conn(
        self,
        conn: sqlite3.Connection,
        user_id: int,
        *,
        session_id: str | None,
        reason: str,
    ) -> dict[str, Any] | None:
        """R3：事务内原子扣减 + audit。v2.3 订阅有效 → no-op。"""
        row = conn.execute(
            "SELECT quota_remaining, membership_status, subscription_expires_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            return None
        if UserRepository().is_subscription_active(dict(row)):
            conn.execute(
                """
                INSERT INTO quota_audit (user_id, delta, reason, session_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, 0, f"{reason}:subscription_no_op", session_id, _now()),
            )
            return None
        if row["quota_remaining"] <= 0:
            return None
        conn.execute(
            "UPDATE users SET quota_remaining = quota_remaining - 1, updated_at = ? WHERE id = ?",
            (_now(), user_id),
        )
        conn.execute(
            """
            INSERT INTO quota_audit (user_id, delta, reason, session_id, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, -1, reason, session_id, _now()),
        )
        return None

    def compensate_quota_in_conn(
        self,
        conn: sqlite3.Connection,
        user_id: int,
        *,
        session_id: str | None,
        reason: str,
    ) -> None:
        """R3：事务内 +1 补偿。v2.3 订阅有效 → no-op。"""
        row = conn.execute(
            "SELECT membership_status, subscription_expires_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            return
        if UserRepository().is_subscription_active(dict(row)):
            conn.execute(
                """
                INSERT INTO quota_audit (user_id, delta, reason, session_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, 0, f"{reason}:subscription_no_op", session_id, _now()),
            )
            return
        conn.execute(
            "UPDATE users SET quota_remaining = quota_remaining + 1, updated_at = ? WHERE id = ?",
            (_now(), user_id),
        )
        conn.execute(
            """
            INSERT INTO quota_audit (user_id, delta, reason, session_id, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, +1, reason, session_id, _now()),
        )
