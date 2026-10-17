"""R1: Message repository — 消息 CRUD + (session_id, request_id) 幂等。"""
from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any

from app.db.repositories.base import BaseRepository, _loads, _now


class MessageRepository(BaseRepository):
    def create_message(
        self,
        *,
        session_id: str,
        role: str,
        kind: str,
        content: str,
        meta: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        from app.db.transaction import with_retry

        def _do() -> dict[str, Any]:
            with self.get_connection() as conn:
                return self.create_message_in_conn(
                    conn,
                    session_id=session_id,
                    role=role,
                    kind=kind,
                    content=content,
                    meta=meta,
                    request_id=request_id,
                )

        return with_retry(_do)

    def create_message_in_conn(
        self,
        conn: sqlite3.Connection,
        *,
        session_id: str,
        role: str,
        kind: str,
        content: str,
        meta: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        if request_id:
            row = conn.execute(
                "SELECT * FROM messages WHERE session_id = ? AND request_id = ?",
                (session_id, request_id),
            ).fetchone()
            if row is not None:
                return {
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "seq": row["seq"],
                    "role": row["role"],
                    "kind": row["kind"],
                    "content": row["content"],
                    "created_at": row["created_at"],
                    "meta": _loads(row["meta_json"], {}),
                }
        seq_row = conn.execute(
            "SELECT COALESCE(MAX(seq), 0) AS max_seq FROM messages WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        seq = int(seq_row["max_seq"]) + 1
        message_id = str(uuid.uuid4())
        timestamp = _now()
        conn.execute(
            """
            INSERT INTO messages (id, session_id, seq, role, kind, content, created_at, meta_json, request_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                session_id,
                seq,
                role,
                kind,
                content,
                timestamp,
                json.dumps(meta or {}, ensure_ascii=False),
                request_id,
            ),
        )
        return {
            "id": message_id,
            "session_id": session_id,
            "seq": seq,
            "role": role,
            "kind": kind,
            "content": content,
            "created_at": timestamp,
            "meta": meta or {},
        }

    def find_message_by_request_id(
        self, session_id: str, request_id: str
    ) -> dict[str, Any] | None:
        with self.get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM messages
                WHERE session_id = ? AND request_id = ?
                """,
                (session_id, request_id),
            ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "session_id": row["session_id"],
            "seq": row["seq"],
            "role": row["role"],
            "kind": row["kind"],
            "content": row["content"],
            "created_at": row["created_at"],
            "meta": _loads(row["meta_json"], {}),
        }

    def find_message_pair_by_request_id(
        self, session_id: str, request_id: str
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        user = self.find_message_by_request_id(session_id, request_id)
        if not user:
            return None, None
        with self.get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM messages
                WHERE session_id = ? AND seq = ? AND role = 'assistant'
                """,
                (session_id, int(user["seq"]) + 1),
            ).fetchone()
        if not row:
            return user, None
        return user, {
            "id": row["id"],
            "session_id": row["session_id"],
            "seq": row["seq"],
            "role": row["role"],
            "kind": row["kind"],
            "content": row["content"],
            "created_at": row["created_at"],
            "meta": _loads(row["meta_json"], {}),
        }

    def list_messages(self, session_id: str) -> list[dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY seq ASC",
                (session_id,),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "session_id": row["session_id"],
                "seq": row["seq"],
                "role": row["role"],
                "kind": row["kind"],
                "content": row["content"],
                "created_at": row["created_at"],
                "meta": _loads(row["meta_json"], {}),
            }
            for row in rows
        ]
