"""R1: Session repository — 面试会话 CRUD + workflow_state 更新。"""
from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any

from app.core.constants import V2_SESSION_SCHEMA_VERSION
from app.core.logging_utils import log_payload
from app.db.repositories.base import BaseRepository, _loads, _now
import logging

logger = logging.getLogger("uvicorn.error")

# 4.2：白名单列名映射
_SESSION_UPDATABLE_COLUMNS: dict[str, set[str]] = {
    "interview_sessions": {
        "status",
        "workflow_state_json",
        "evaluation_json",
        "confirmed_plan_id",
        "profile_json",
        "title",
        "target_role",
        "resume_id",
        "configuration_json",
    },
    "interview_plans": {"status"},
    "users": {"quota_remaining", "password_hash", "tier", "subscription_expires_at"},
}


def _assert_known_column(table: str, column: str) -> None:
    allowed = _SESSION_UPDATABLE_COLUMNS.get(table)
    if not allowed or column not in allowed:
        raise ValueError(f"refusing to update non-whitelisted column {table}.{column}")


class SessionRepository(BaseRepository):
    # ----- Planning session lifecycle -----
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
        with self.get_connection() as conn:
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
        from app.db.transaction import with_retry

        def _do() -> None:
            with self.get_connection() as conn:
                self.update_planning_session_in_conn(
                    conn,
                    session_id,
                    status=status,
                    confirmed_plan_id=confirmed_plan_id,
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
        with self.get_connection() as conn:
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
            "messages": self._list_messages_internal(session_id),
        }

    def list_v2_session_rows(self, user_id: int) -> list[dict[str, Any]]:
        with self.get_connection() as conn:
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

    # ----- Session update (transaction) -----
    def update_session(
        self,
        session_id: str,
        *,
        status: str | None = None,
        workflow_state: dict[str, Any] | None = None,
        evaluation: dict[str, Any] | None = None,
    ) -> None:
        from app.db.transaction import with_retry

        def _do() -> None:
            with self.get_connection() as conn:
                self.update_session_in_conn(
                    conn,
                    session_id,
                    status=status,
                    workflow_state=workflow_state,
                    evaluation=evaluation,
                )
                conn.commit()

        with_retry(_do)

    def _build_session_update(
        self,
        *,
        status: str | None,
        workflow_state: dict[str, Any] | None,
        evaluation: dict[str, Any] | None,
        include_version_bump: bool = True,
    ) -> tuple[str, list[Any]]:
        assignments: list[str] = ["updated_at = ?"]
        params: list[Any] = [_now()]
        if status is not None:
            _assert_known_column("interview_sessions", "status")
            assignments.append("status = ?")
            params.append(status)
        if workflow_state is not None:
            _assert_known_column("interview_sessions", "workflow_state_json")
            assignments.append("workflow_state_json = ?")
            params.append(json.dumps(workflow_state, ensure_ascii=False))
        if evaluation is not None:
            _assert_known_column("interview_sessions", "evaluation_json")
            assignments.append("evaluation_json = ?")
            params.append(json.dumps(evaluation, ensure_ascii=False))
        if include_version_bump:
            assignments.append("version = version + 1")
        sql = "UPDATE interview_sessions SET " + ", ".join(assignments) + " WHERE id = ?"
        return sql, params

    def update_session_in_conn(
        self,
        conn: sqlite3.Connection,
        session_id: str,
        *,
        status: str | None = None,
        workflow_state: dict[str, Any] | None = None,
        evaluation: dict[str, Any] | None = None,
    ) -> None:
        sql, params = self._build_session_update(
            status=status, workflow_state=workflow_state, evaluation=evaluation
        )
        params.append(session_id)
        conn.execute(sql, tuple(params))

    def update_planning_session_in_conn(
        self,
        conn: sqlite3.Connection,
        session_id: str,
        *,
        status: str | None = None,
        confirmed_plan_id: str | None = None,
    ) -> None:
        assignments: list[str] = ["updated_at = ?"]
        params: list[Any] = [_now()]
        if status is not None:
            _assert_known_column("interview_sessions", "status")
            assignments.append("status = ?")
            params.append(status)
        if confirmed_plan_id is not None:
            _assert_known_column("interview_sessions", "confirmed_plan_id")
            assignments.append("confirmed_plan_id = ?")
            params.append(confirmed_plan_id)
        params.append(session_id)
        conn.execute(
            "UPDATE interview_sessions SET " + ", ".join(assignments) + " WHERE id = ?",
            tuple(params),
        )

    # ----- Internal: messages readout -----
    def _list_messages_internal(self, session_id: str) -> list[dict[str, Any]]:
        """子 repo 共用：session_record 读 messages。"""
        from app.db.repositories.message_repo import MessageRepository
        return MessageRepository().list_messages(session_id)
