"""R1: Lock repository — session_locks（v2.3 lock_type 列）。"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db.repositories.base import BaseRepository, _now


class LockRepository(BaseRepository):
    def acquire_session_lock(
        self,
        session_id: str,
        *,
        lock_token: str,
        ttl_seconds: int,
        lock_type: str = "session",
        lock_key: str | None = None,
    ) -> dict[str, Any] | None:
        now_ts = _now()
        now_dt = datetime.now(timezone.utc)
        expires_at = (now_dt + timedelta(seconds=ttl_seconds)).isoformat()
        key = lock_key or f"{lock_type}:{session_id}"

        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT lock_token, expires_at FROM session_locks WHERE lock_key = ?",
                (key,),
            ).fetchone()
            if row is None:
                try:
                    conn.execute(
                        """
                        INSERT INTO session_locks (lock_key, session_id, lock_type, lock_token, expires_at, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (key, session_id, lock_type, lock_token, expires_at, now_ts),
                    )
                    conn.commit()
                except sqlite3.IntegrityError:
                    conn.rollback()
                    fresh = conn.execute(
                        "SELECT lock_token, expires_at FROM session_locks WHERE lock_key = ?",
                        (key,),
                    ).fetchone()
                    if fresh is not None:
                        existing_dt = datetime.fromisoformat(str(fresh["expires_at"]))
                        remaining = max(0, int((existing_dt - now_dt).total_seconds()))
                        return {"locked": True, "remaining_seconds": remaining, "lock_type": lock_type}
                    return {"locked": True, "remaining_seconds": ttl_seconds, "lock_type": lock_type}
                return {"lock_token": lock_token, "expires_at": expires_at, "lock_type": lock_type}
            existing_token = str(row["lock_token"])
            existing_expires = str(row["expires_at"])
            existing_dt = datetime.fromisoformat(existing_expires)
            if existing_token == lock_token or existing_dt <= now_dt:
                conn.execute(
                    """
                    UPDATE session_locks
                    SET lock_token = ?, expires_at = ?, created_at = ?, lock_type = ?
                    WHERE lock_key = ?
                    """,
                    (lock_token, expires_at, now_ts, lock_type, key),
                )
                conn.commit()
                return {"lock_token": lock_token, "expires_at": expires_at, "lock_type": lock_type}
            remaining = max(0, int((existing_dt - now_dt).total_seconds()))
            return {"locked": True, "remaining_seconds": remaining, "lock_type": lock_type}

    def release_session_lock(
        self,
        session_id: str,
        *,
        lock_token: str,
        lock_type: str = "session",
        lock_key: str | None = None,
    ) -> bool:
        key = lock_key or f"{lock_type}:{session_id}"
        with self.get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM session_locks WHERE lock_key = ? AND lock_token = ?",
                (key, lock_token),
            )
            conn.commit()
            return cursor.rowcount > 0

    def refresh_session_lock(
        self,
        session_id: str,
        *,
        lock_token: str,
        ttl_seconds: int,
        lock_type: str = "session",
        lock_key: str | None = None,
    ) -> bool:
        key = lock_key or f"{lock_type}:{session_id}"
        with self.get_connection() as conn:
            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat()
            cursor = conn.execute(
                """
                UPDATE session_locks
                SET expires_at = ?
                WHERE lock_key = ? AND lock_token = ?
                """,
                (expires_at, key, lock_token),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_session_lock(
        self,
        session_id: str,
        *,
        lock_type: str = "session",
        lock_key: str | None = None,
    ) -> dict[str, Any] | None:
        key = lock_key or f"{lock_type}:{session_id}"
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM session_locks WHERE lock_key = ?", (key,),
            ).fetchone()
        return dict(row) if row else None

    def get_session_lock_by_type(
        self, session_id: str, lock_type: str,
    ) -> dict[str, Any] | None:
        return self.get_session_lock(session_id, lock_type=lock_type)
