"""R1: Plan repository — 面试计划 CRUD。"""
from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any

from app.db.repositories.base import BaseRepository, _loads, _now


class PlanRepository(BaseRepository):
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
        with self.get_connection() as conn:
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
        with self.get_connection() as conn:
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
        with self.get_connection() as conn:
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
        with self.get_connection() as conn:
            conn.execute("UPDATE interview_plans SET status = ? WHERE id = ?", (status, plan_id))
            conn.commit()

    def get_plan_by_id(self, plan_id: str) -> dict[str, Any]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM interview_plans WHERE id = ?", (plan_id,)).fetchone()
        if not row:
            raise ValueError("plan not found")
        return self._serialize_plan(dict(row))

    def update_interview_plan_status_in_conn(
        self,
        conn: sqlite3.Connection,
        plan_id: str,
        *,
        status: str,
    ) -> None:
        from app.db.repositories.session_repo import _assert_known_column
        _assert_known_column("interview_plans", "status")
        conn.execute(
            "UPDATE interview_plans SET status = ? WHERE id = ?", (status, plan_id),
        )

    def create_interview_plan_in_conn(
        self,
        conn: sqlite3.Connection,
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
        return {
            "id": plan_id,
            "session_id": session_id,
            "version": version,
            "status": status,
            "plan_json": plan_json,
            "candidate_summary_json": candidate_summary_json,
            "regeneration_strategy": regeneration_strategy,
            "focus_topics": focus_topics or [],
            "additional_instruction": additional_instruction,
            "created_at": timestamp,
        }

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
