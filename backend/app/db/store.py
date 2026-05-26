import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from app.core.config import settings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _loads(data: str | None, fallback: Any) -> Any:
    if not data:
        return fallback
    return json.loads(data)


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                quota_remaining INTEGER NOT NULL DEFAULT 5,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS interview_sessions (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                target_role TEXT NOT NULL,
                status TEXT NOT NULL,
                profile_json TEXT NOT NULL,
                workflow_state_json TEXT NOT NULL,
                evaluation_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                seq INTEGER NOT NULL,
                role TEXT NOT NULL,
                kind TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                meta_json TEXT,
                FOREIGN KEY(session_id) REFERENCES interview_sessions(id)
            );

            CREATE TABLE IF NOT EXISTS resumes (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_user_updated ON interview_sessions(user_id, updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_messages_session_seq ON messages(session_id, seq ASC);
            CREATE INDEX IF NOT EXISTS idx_resumes_user_updated ON resumes(user_id, updated_at DESC);
            """
        )
        conn.commit()


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(settings.database_file, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


class Store:
    def create_user(self, username: str, password_hash: str, quota_remaining: int) -> dict[str, Any]:
        timestamp = _now()
        with get_connection() as conn:
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
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    def decrement_quota(self, user_id: int) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute("SELECT quota_remaining FROM users WHERE id = ?", (user_id,)).fetchone()
            if not row or row["quota_remaining"] <= 0:
                return None
            conn.execute(
                "UPDATE users SET quota_remaining = quota_remaining - 1, updated_at = ? WHERE id = ?",
                (_now(), user_id),
            )
            conn.commit()
        return self.get_user_by_id(user_id)

    def create_session(
        self,
        *,
        user_id: int,
        title: str,
        target_role: str,
        status: str,
        profile: dict[str, Any],
        workflow_state: dict[str, Any],
    ) -> dict[str, Any]:
        session_id = str(uuid.uuid4())
        timestamp = _now()
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO interview_sessions (
                    id, user_id, title, target_role, status, profile_json,
                    workflow_state_json, evaluation_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
                """,
                (
                    session_id,
                    user_id,
                    title,
                    target_role,
                    status,
                    json.dumps(profile, ensure_ascii=False),
                    json.dumps(workflow_state, ensure_ascii=False),
                    timestamp,
                    timestamp,
                ),
            )
            conn.commit()
        return self.get_session(user_id, session_id)

    def create_resume(self, *, user_id: int, filename: str, payload: dict[str, Any]) -> dict[str, Any]:
        resume_id = str(uuid.uuid4())
        timestamp = _now()
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO resumes (id, user_id, filename, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (resume_id, user_id, filename, json.dumps(payload, ensure_ascii=False), timestamp, timestamp),
            )
            conn.commit()
        return self.get_resume(user_id, resume_id)

    def update_session(
        self,
        session_id: str,
        *,
        status: str | None = None,
        workflow_state: dict[str, Any] | None = None,
        evaluation: dict[str, Any] | None = None,
    ) -> None:
        assignments: list[str] = ["updated_at = ?"]
        params: list[Any] = [_now()]
        if status is not None:
            assignments.append("status = ?")
            params.append(status)
        if workflow_state is not None:
            assignments.append("workflow_state_json = ?")
            params.append(json.dumps(workflow_state, ensure_ascii=False))
        if evaluation is not None:
            assignments.append("evaluation_json = ?")
            params.append(json.dumps(evaluation, ensure_ascii=False))
        params.append(session_id)
        with get_connection() as conn:
            conn.execute(f"UPDATE interview_sessions SET {', '.join(assignments)} WHERE id = ?", tuple(params))
            conn.commit()

    def list_sessions(self, user_id: int) -> list[dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM interview_sessions WHERE user_id = ? ORDER BY updated_at DESC",
                (user_id,),
            ).fetchall()
        return [self._serialize_session(dict(row), include_messages=False) for row in rows]

    def get_session(self, user_id: int, session_id: str) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM interview_sessions WHERE id = ? AND user_id = ?",
                (session_id, user_id),
            ).fetchone()
        return self._serialize_session(dict(row)) if row else None

    def list_resumes(self, user_id: int) -> list[dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute("SELECT * FROM resumes WHERE user_id = ? ORDER BY updated_at DESC", (user_id,)).fetchall()
        return [self._serialize_resume(dict(row)) for row in rows]

    def get_resume(self, user_id: int, resume_id: str) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM resumes WHERE id = ? AND user_id = ?", (resume_id, user_id)).fetchone()
        return self._serialize_resume(dict(row)) if row else None

    def delete_resume(self, user_id: int, resume_id: str) -> bool:
        with get_connection() as conn:
            cursor = conn.execute("DELETE FROM resumes WHERE id = ? AND user_id = ?", (resume_id, user_id))
            conn.commit()
            return cursor.rowcount > 0

    def create_message(
        self,
        *,
        session_id: str,
        role: str,
        kind: str,
        content: str,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with get_connection() as conn:
            seq_row = conn.execute(
                "SELECT COALESCE(MAX(seq), 0) AS max_seq FROM messages WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            seq = int(seq_row["max_seq"]) + 1
            message_id = str(uuid.uuid4())
            timestamp = _now()
            conn.execute(
                """
                INSERT INTO messages (id, session_id, seq, role, kind, content, created_at, meta_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )
            conn.commit()
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

    def list_messages(self, session_id: str) -> list[dict[str, Any]]:
        with get_connection() as conn:
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

    def _serialize_session(self, row: dict[str, Any], include_messages: bool = True) -> dict[str, Any]:
        session = {
            "id": row["id"],
            "user_id": row["user_id"],
            "title": row["title"],
            "target_role": row["target_role"],
            "status": row["status"],
            "profile": _loads(row["profile_json"], {}),
            "workflow_state": _loads(row["workflow_state_json"], {}),
            "evaluation": _loads(row["evaluation_json"], None),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        session["messages"] = self.list_messages(row["id"]) if include_messages else []
        return session

    @staticmethod
    def _serialize_resume(row: dict[str, Any]) -> dict[str, Any]:
        payload = _loads(row["payload_json"], {})
        return {
            "id": row["id"],
            "filename": row["filename"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "personal_info": payload.get("personal_info", ""),
            "highlights": payload.get("highlights", []),
            "technical_skills": payload.get("technical_skills", []),
            "resume_text": payload.get("resume_text", ""),
            "work_experience": payload.get("work_experience", []),
            "project_experience": payload.get("project_experience", []),
            "model_provider": payload.get("model_provider", "mock"),
            "model_name": payload.get("model_name", ""),
        }
