"""R1: Resume repository — 简历 CRUD。"""
from __future__ import annotations

import json
import uuid
from typing import Any

from app.db.repositories.base import BaseRepository, _loads, _now


class ResumeRepository(BaseRepository):
    def create_resume(self, *, user_id: int, filename: str, payload: dict[str, Any]) -> dict[str, Any]:
        resume_id = str(uuid.uuid4())
        timestamp = _now()
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO resumes (id, user_id, filename, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (resume_id, user_id, filename, json.dumps(payload, ensure_ascii=False), timestamp, timestamp),
            )
            conn.commit()
        return self.get_resume(user_id, resume_id)

    def list_resumes(self, user_id: int) -> list[dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM resumes WHERE user_id = ? ORDER BY updated_at DESC", (user_id,),
            ).fetchall()
        return [self._serialize_resume(dict(row)) for row in rows]

    def get_resume(self, user_id: int, resume_id: str) -> dict[str, Any] | None:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM resumes WHERE id = ? AND user_id = ?", (resume_id, user_id),
            ).fetchone()
        return self._serialize_resume(dict(row)) if row else None

    def delete_resume(self, user_id: int, resume_id: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM resumes WHERE id = ? AND user_id = ?", (resume_id, user_id),
            )
            conn.commit()
            return cursor.rowcount > 0

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
