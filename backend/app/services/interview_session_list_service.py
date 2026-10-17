"""V2 面试记录列表（06 小步 1 补全）。"""
from __future__ import annotations

from typing import Any

from app.db.store import Store
from app.services.interview.boundaries import is_past_deadline, resolve_display_remaining_seconds
from app.services.interview_configuration_service import configuration_labels
from app.services.interview_agent_service import InterviewAgentService


class InterviewSessionListService:
    def __init__(self) -> None:
        self.store = Store()
        self.live_service = InterviewAgentService()

    def list_v2_sessions(self, user_id: int) -> list[dict[str, Any]]:
        rows = self.store.list_v2_session_rows(user_id)
        items: list[dict[str, Any]] = []
        for row in rows:
            item = self._build_list_item(user_id, row)
            if item:
                items.append(item)
        return items

    def _build_list_item(self, user_id: int, row: dict[str, Any]) -> dict[str, Any] | None:
        session_id = str(row["id"])
        status = str(row["status"])
        workflow_state = row.get("workflow_state") or {}
        evaluation = row.get("evaluation")

        if status == "active":
            deadline_at = str(workflow_state.get("deadline_at") or "")
            if is_past_deadline(deadline_at):
                self.live_service.finish_interview(user_id, session_id, reason="stale_deadline_reached")
                refreshed = self.store.get_interview_session_record(user_id, session_id)
                if not refreshed:
                    return None
                status = str(refreshed["status"])
                workflow_state = refreshed.get("workflow_state") or {}
                evaluation = refreshed.get("evaluation")
                row = {
                    **row,
                    "status": status,
                    "workflow_state": workflow_state,
                    "evaluation": evaluation,
                    "updated_at": refreshed["updated_at"],
                }

        remaining = self._resolve_remaining_seconds(
            status=status,
            workflow_state=workflow_state,
            updated_at=str(row.get("updated_at") or ""),
        )
        display_label, action_label, action_path = self._resolve_ui(
            session_id=session_id,
            status=status,
            remaining_seconds=remaining,
            workflow_state=workflow_state if isinstance(workflow_state, dict) else {},
        )
        config_fields = self._configuration_fields(row.get("configuration") or {})
        evaluation_fields = self._evaluation_fields(evaluation if isinstance(evaluation, dict) else None)
        session_at = str((workflow_state or {}).get("started_at") or row.get("created_at") or row.get("updated_at"))
        return {
            "id": session_id,
            "title": row["title"],
            "target_role": row["target_role"],
            "target_role_label": config_fields["target_role_label"],
            "target_level": config_fields["target_level"],
            "target_level_label": config_fields["target_level_label"],
            "duration_minutes": config_fields["duration_minutes"],
            "overall_score": evaluation_fields["overall_score"],
            "scored_topic_count": evaluation_fields["scored_topic_count"],
            "total_topic_count": evaluation_fields["total_topic_count"],
            "status": status,
            "display_label": display_label,
            "action_label": action_label,
            "action_path": action_path,
            "remaining_seconds": remaining,
            "has_evaluation": bool(evaluation),
            "session_at": session_at,
            "updated_at": row["updated_at"],
            "created_at": row["created_at"],
        }

    @staticmethod
    def _resolve_remaining_seconds(
        *,
        status: str,
        workflow_state: dict[str, Any],
        updated_at: str,
    ) -> int | None:
        deadline_at = str(workflow_state.get("deadline_at") or "")
        if not deadline_at:
            return None
        return resolve_display_remaining_seconds(
            deadline_at=deadline_at,
            runtime_state=workflow_state,
            session_status=status,
            session_updated_at=updated_at,
        )

    @staticmethod
    def _resolve_ui(
        *,
        session_id: str,
        status: str,
        remaining_seconds: int | None,
        workflow_state: dict[str, Any],
    ) -> tuple[str, str, str]:
        base = f"/interviews/{session_id}"
        finish_reason = str(workflow_state.get("finish_reason") or "")
        if status == "completed":
            return "completed", "查看评估报告", f"{base}/evaluation"
        if status == "evaluating":
            if finish_reason == "stale_deadline_reached":
                return "pending_evaluation", "生成评估报告", f"{base}/evaluation"
            return "evaluating", "查看评估报告", f"{base}/evaluation"
        if status == "active":
            if remaining_seconds is not None and remaining_seconds <= 0:
                return "pending_evaluation", "生成评估报告", f"{base}/evaluation"
            return "in_progress", "继续面试", f"{base}/live"
        if status in {"planning", "plan_ready", "plan_confirmed"}:
            return "not_started", "开始面试", f"{base}/plan"
        return "not_started", "开始面试", f"{base}/live"

    @staticmethod
    def _configuration_fields(configuration: dict[str, Any]) -> dict[str, Any]:
        if not configuration:
            return {
                "target_role_label": "",
                "target_level": "",
                "target_level_label": "",
                "duration_minutes": 45,
            }
        labels = configuration_labels(configuration)
        return {
            "target_role_label": labels.get("target_role_label") or str(configuration.get("target_role", "")),
            "target_level": str(configuration.get("target_level", "")),
            "target_level_label": labels.get("target_level_label") or str(configuration.get("target_level", "")),
            "duration_minutes": int(configuration.get("duration_minutes") or 45),
        }

    @staticmethod
    def _evaluation_fields(evaluation: dict[str, Any] | None) -> dict[str, Any]:
        if not evaluation:
            return {
                "overall_score": None,
                "scored_topic_count": None,
                "total_topic_count": None,
            }
        coverage = evaluation.get("coverage") or {}
        overall_score = evaluation.get("overall_score")
        return {
            "overall_score": int(overall_score) if overall_score is not None else None,
            "scored_topic_count": coverage.get("scored_topic_count"),
            "total_topic_count": coverage.get("total_topic_count"),
        }
