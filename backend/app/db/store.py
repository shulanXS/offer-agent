import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from app.core.config import settings
from app.core.constants import V2_SESSION_SCHEMA_VERSION


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _loads(data: str | None, fallback: Any) -> Any:
    if not data:
        return fallback
    return json.loads(data)


def init_db() -> None:
    with get_connection() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
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
                request_id TEXT,
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

            CREATE TABLE IF NOT EXISTS interview_plans (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                status TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                candidate_summary_json TEXT NOT NULL,
                regeneration_strategy TEXT,
                focus_topics_json TEXT,
                additional_instruction TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES interview_sessions(id)
            );

            CREATE INDEX IF NOT EXISTS idx_interview_plans_session_version
                ON interview_plans(session_id, version DESC);

            CREATE TABLE IF NOT EXISTS user_learning_profiles (
                user_id INTEGER NOT NULL,
                resume_id TEXT NOT NULL,
                target_role TEXT NOT NULL,
                interview_type TEXT NOT NULL,
                profile_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (user_id, resume_id, target_role, interview_type)
            );

            CREATE TABLE IF NOT EXISTS learning_session_outcomes (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                resume_id TEXT NOT NULL,
                session_id TEXT NOT NULL UNIQUE,
                target_role TEXT NOT NULL,
                interview_type TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                outcome_json TEXT NOT NULL,
                deleted_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_learning_outcomes_profile
                ON learning_session_outcomes(user_id, resume_id, target_role, interview_type, completed_at ASC);
            """
        )
        _ensure_column(conn, "interview_sessions", "resume_id", "TEXT")
        _ensure_column(conn, "interview_sessions", "configuration_json", "TEXT")
        _ensure_column(conn, "interview_sessions", "confirmed_plan_id", "TEXT")
        _ensure_column(conn, "interview_sessions", "version", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "messages", "request_id", "TEXT")
        _ensure_index(
            conn,
            "messages",
            "uniq_messages_request_id",
            "CREATE UNIQUE INDEX uniq_messages_request_id ON messages(session_id, request_id) WHERE request_id IS NOT NULL",
        )
        conn.commit()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    existing = {row[1] for row in rows}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _ensure_index(conn: sqlite3.Connection, table: str, name: str, definition: str) -> None:
    rows = conn.execute(f"PRAGMA index_list({table})").fetchall()
    existing = {row[1] for row in rows}
    if name not in existing:
        conn.execute(definition)


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

    def update_user_password_hash(self, user_id: int, password_hash: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                (password_hash, _now(), user_id),
            )
            conn.commit()

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

    def create_planning_session(
        self,
        *,
        user_id: int,
        title: str,
        target_role: str,
        resume_id: str,
        configuration: dict[str, Any],
    ) -> dict[str, Any]:
        session_id = str(uuid.uuid4())
        timestamp = _now()
        profile = {
            "schema_version": V2_SESSION_SCHEMA_VERSION,
            "resume_id": resume_id,
            "configuration": configuration,
        }
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO interview_sessions (
                    id, user_id, title, target_role, status, profile_json,
                    workflow_state_json, evaluation_json, resume_id, configuration_json,
                    confirmed_plan_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, NULL, ?, ?)
                """,
                (
                    session_id,
                    user_id,
                    title,
                    target_role,
                    "planning",
                    json.dumps(profile, ensure_ascii=False),
                    json.dumps({}, ensure_ascii=False),
                    resume_id,
                    json.dumps(configuration, ensure_ascii=False),
                    timestamp,
                    timestamp,
                ),
            )
            conn.commit()
        return self.get_planning_session(user_id, session_id)

    def update_planning_session(
        self,
        session_id: str,
        *,
        status: str | None = None,
        confirmed_plan_id: str | None = None,
    ) -> None:
        assignments: list[str] = ["updated_at = ?"]
        params: list[Any] = [_now()]
        if status is not None:
            assignments.append("status = ?")
            params.append(status)
        if confirmed_plan_id is not None:
            assignments.append("confirmed_plan_id = ?")
            params.append(confirmed_plan_id)
        params.append(session_id)
        from app.db.transaction import with_retry

        def _do() -> None:
            with get_connection() as conn:
                conn.execute(
                    f"UPDATE interview_sessions SET {', '.join(assignments)} WHERE id = ?",
                    tuple(params),
                )
                conn.commit()

        with_retry(_do)

    def get_planning_session(self, user_id: int, session_id: str) -> dict[str, Any] | None:
        record = self.get_interview_session_record(user_id, session_id)
        if not record:
            return None
        configuration = record.get("configuration")
        if not configuration:
            return None
        return {
            "id": record["id"],
            "user_id": record["user_id"],
            "title": record["title"],
            "target_role": record["target_role"],
            "status": record["status"],
            "resume_id": record.get("resume_id") or configuration.get("resume_id", ""),
            "configuration": configuration,
            "confirmed_plan_id": record.get("confirmed_plan_id"),
            "created_at": record["created_at"],
            "updated_at": record["updated_at"],
        }

    def get_interview_session_record(self, user_id: int, session_id: str) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM interview_sessions WHERE id = ? AND user_id = ?",
                (session_id, user_id),
            ).fetchone()
        if not row:
            return None
        session = dict(row)
        profile = _loads(session.get("profile_json"), {})
        configuration = _loads(session.get("configuration_json"), None)
        if configuration is None and profile.get("schema_version") == V2_SESSION_SCHEMA_VERSION:
            configuration = profile.get("configuration", {})
        if not configuration and profile.get("schema_version") != V2_SESSION_SCHEMA_VERSION:
            return None
        return {
            "id": session["id"],
            "user_id": session["user_id"],
            "title": session["title"],
            "target_role": session["target_role"],
            "status": session["status"],
            "resume_id": session.get("resume_id") or configuration.get("resume_id", ""),
            "configuration": configuration,
            "confirmed_plan_id": session.get("confirmed_plan_id"),
            "workflow_state": _loads(session.get("workflow_state_json"), {}),
            "evaluation": _loads(session.get("evaluation_json"), None),
            "created_at": session["created_at"],
            "updated_at": session["updated_at"],
            "messages": self.list_messages(session_id),
        }

    def create_interview_plan(
        self,
        *,
        session_id: str,
        version: int,
        status: str,
        plan_json: dict[str, Any],
        candidate_summary_json: dict[str, Any],
        regeneration_strategy: str | None = None,
        focus_topics: list[str] | None = None,
        additional_instruction: str | None = None,
    ) -> dict[str, Any]:
        plan_id = str(uuid.uuid4())
        timestamp = _now()
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO interview_plans (
                    id, session_id, version, status, plan_json, candidate_summary_json,
                    regeneration_strategy, focus_topics_json, additional_instruction, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    session_id,
                    version,
                    status,
                    json.dumps(plan_json, ensure_ascii=False),
                    json.dumps(candidate_summary_json, ensure_ascii=False),
                    regeneration_strategy,
                    json.dumps(focus_topics or [], ensure_ascii=False),
                    additional_instruction,
                    timestamp,
                ),
            )
            conn.commit()
        return self.get_plan_by_id(plan_id)

    def get_latest_plan(self, session_id: str) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM interview_plans
                WHERE session_id = ?
                ORDER BY version DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
        return self._serialize_plan(dict(row)) if row else None

    def list_plans_for_session(self, session_id: str) -> list[dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM interview_plans
                WHERE session_id = ?
                ORDER BY version ASC
                """,
                (session_id,),
            ).fetchall()
        return [self._serialize_plan(dict(row)) for row in rows]

    def update_interview_plan_status(self, plan_id: str, *, status: str) -> None:
        with get_connection() as conn:
            conn.execute("UPDATE interview_plans SET status = ? WHERE id = ?", (status, plan_id))
            conn.commit()

    def get_plan_by_id(self, plan_id: str) -> dict[str, Any]:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM interview_plans WHERE id = ?", (plan_id,)).fetchone()
        if not row:
            raise ValueError("plan not found")
        return self._serialize_plan(dict(row))

    @staticmethod
    def _serialize_plan(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "session_id": row["session_id"],
            "version": row["version"],
            "status": row["status"],
            "plan_json": _loads(row["plan_json"], {}),
            "candidate_summary_json": _loads(row["candidate_summary_json"], {}),
            "regeneration_strategy": row.get("regeneration_strategy"),
            "focus_topics": _loads(row.get("focus_topics_json"), []),
            "additional_instruction": row.get("additional_instruction"),
            "created_at": row["created_at"],
        }

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
        assignments: list[str] = ["updated_at = ?", "version = version + 1"]
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
        from app.db.transaction import with_retry

        def _do() -> None:
            with get_connection() as conn:
                conn.execute(
                    f"UPDATE interview_sessions SET {', '.join(assignments)} WHERE id = ?",
                    tuple(params),
                )
                conn.commit()

        with_retry(_do)

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
        request_id: str | None = None,
    ) -> dict[str, Any]:
        # A2：若提供了 request_id 且已存在同 session_id+request_id 的消息，直接返回原结果
        if request_id:
            existing = self._find_message_by_request_id(session_id, request_id)
            if existing is not None:
                return existing
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

    def find_message_by_request_id(
        self, session_id: str, request_id: str
    ) -> dict[str, Any] | None:
        """A2 公开接口：按 (session_id, request_id) 查找消息。"""
        return self._find_message_by_request_id(session_id, request_id)

    def _find_message_by_request_id(
        self, session_id: str, request_id: str
    ) -> dict[str, Any] | None:
        with get_connection() as conn:
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

    def list_v2_session_rows(self, user_id: int) -> list[dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, title, target_role, status, workflow_state_json, evaluation_json,
                       configuration_json, created_at, updated_at
                FROM interview_sessions
                WHERE user_id = ?
                  AND configuration_json IS NOT NULL
                  AND TRIM(configuration_json) != ''
                ORDER BY updated_at DESC
                """,
                (user_id,),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "title": row["title"],
                "target_role": row["target_role"],
                "status": row["status"],
                "workflow_state": _loads(row["workflow_state_json"], {}),
                "evaluation": _loads(row["evaluation_json"], None),
                "configuration": _loads(row["configuration_json"], {}),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def insert_learning_outcome(
        self,
        *,
        outcome_id: str,
        user_id: int,
        resume_id: str,
        session_id: str,
        target_role: str,
        interview_type: str,
        completed_at: str,
        outcome_json: dict[str, Any],
    ) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO learning_session_outcomes (
                    id, user_id, resume_id, session_id, target_role, interview_type,
                    completed_at, outcome_json, deleted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    outcome_id,
                    user_id,
                    resume_id,
                    session_id,
                    target_role,
                    interview_type,
                    completed_at,
                    json.dumps(outcome_json, ensure_ascii=False),
                ),
            )
            conn.commit()

    def update_learning_outcome(
        self,
        session_id: str,
        *,
        outcome_json: dict[str, Any],
        completed_at: str,
    ) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE learning_session_outcomes
                SET outcome_json = ?, completed_at = ?
                WHERE session_id = ? AND deleted_at IS NULL
                """,
                (json.dumps(outcome_json, ensure_ascii=False), completed_at, session_id),
            )
            conn.commit()

    def get_learning_outcome_by_session(self, session_id: str) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM learning_session_outcomes
                WHERE session_id = ? AND deleted_at IS NULL
                """,
                (session_id,),
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["outcome_json"] = _loads(data.get("outcome_json"), {})
        return data

    def delete_learning_outcome(self, session_id: str) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE learning_session_outcomes
                SET deleted_at = ?
                WHERE session_id = ? AND deleted_at IS NULL
                """,
                (_now(), session_id),
            )
            conn.commit()

    def list_learning_outcomes(
        self,
        *,
        user_id: int,
        resume_id: str,
        target_role: str,
        interview_type: str,
    ) -> list[dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM learning_session_outcomes
                WHERE user_id = ? AND resume_id = ? AND target_role = ? AND interview_type = ?
                  AND deleted_at IS NULL
                ORDER BY completed_at ASC
                """,
                (user_id, resume_id, target_role, interview_type),
            ).fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            data = dict(row)
            data["outcome_json"] = _loads(data.get("outcome_json"), {})
            results.append(data)
        return results

    def upsert_learning_profile(
        self,
        *,
        user_id: int,
        resume_id: str,
        target_role: str,
        interview_type: str,
        profile_json: dict[str, Any],
    ) -> None:
        timestamp = _now()
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO user_learning_profiles (
                    user_id, resume_id, target_role, interview_type, profile_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, resume_id, target_role, interview_type)
                DO UPDATE SET profile_json = excluded.profile_json, updated_at = excluded.updated_at
                """,
                (
                    user_id,
                    resume_id,
                    target_role,
                    interview_type,
                    json.dumps(profile_json, ensure_ascii=False),
                    timestamp,
                ),
            )
            conn.commit()

    def get_learning_profile(
        self,
        user_id: int,
        resume_id: str,
        target_role: str,
        interview_type: str,
    ) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM user_learning_profiles
                WHERE user_id = ? AND resume_id = ? AND target_role = ? AND interview_type = ?
                """,
                (user_id, resume_id, target_role, interview_type),
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["profile_json"] = _loads(data.get("profile_json"), {})
        return data

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
            "model_provider": payload.get("model_provider", ""),
            "model_name": payload.get("model_name", ""),
        }
