"""R1: Learning repository — learning_session_outcomes + user_learning_profiles。"""
from __future__ import annotations

import json
from typing import Any

from app.db.repositories.base import BaseRepository, _loads, _now


class LearningRepository(BaseRepository):
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
        with self.get_connection() as conn:
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
        with self.get_connection() as conn:
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
        with self.get_connection() as conn:
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
        with self.get_connection() as conn:
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
        with self.get_connection() as conn:
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
        with self.get_connection() as conn:
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
        with self.get_connection() as conn:
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
