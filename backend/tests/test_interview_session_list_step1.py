import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.db.store import Store
from app.main import app

client = TestClient(app)


def _auth_headers() -> dict[str, str]:
    username = f"list_{uuid.uuid4().hex[:8]}"
    password = "password123"
    register_response = client.post("/api/auth/register", json={"username": username, "password": password})
    if register_response.status_code == 409:
        login_response = client.post("/api/auth/login", json={"username": username, "password": password})
        token = login_response.json()["access_token"]
    else:
        token = register_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_ready_resume(headers: dict[str, str]) -> str:
    user_response = client.get("/api/auth/me", headers=headers)
    user_id = user_response.json()["id"]
    store = Store()
    resume = store.create_resume(
        user_id=user_id,
        filename="demo.txt",
        payload={
            "personal_info": "张三，Java 后端开发",
            "highlights": ["项目深挖"],
            "technical_skills": ["Java", "Spring"],
            "resume_text": "姓名：张三\n熟悉 Java 和后端开发。",
            "work_experience": [{"name": "某科技公司", "detail": "负责订单系统后端开发"}],
            "project_experience": [{"name": "订单系统", "detail": "高并发订单处理"}],
            "model_provider": "openai",
            "model_name": "",
        },
    )
    return resume["id"]


def _create_confirmed_session(headers: dict[str, str]) -> str:
    resume_id = _create_ready_resume(headers)
    created = client.post(
        "/api/interviews",
        headers=headers,
        json={
            "resume_id": resume_id,
            "interview_type": "experienced",
            "target_role": "backend",
            "language": "java",
            "target_level": "intermediate",
            "duration_minutes": 45,
            "focus_topics": ["项目深挖"],
            "jd_text": "",
        },
    ).json()
    session_id = created["session_id"]
    client.post(f"/api/interviews/{session_id}/plan/confirm", headers=headers)
    return session_id


def _find_session(items: list[dict], session_id: str) -> dict:
    matched = next(item for item in items if item["id"] == session_id)
    return matched


def test_list_v2_sessions_not_started_after_plan_confirm() -> None:
    headers = _auth_headers()
    session_id = _create_confirmed_session(headers)

    listed = client.get("/api/interviews", headers=headers)
    assert listed.status_code == 200
    item = _find_session(listed.json(), session_id)
    assert item["status"] == "plan_confirmed"
    assert item["display_label"] == "not_started"
    assert item["action_label"] == "开始面试"
    assert item["action_path"].endswith("/live")
    assert item["target_role_label"] == "后端开发"
    assert item["target_level_label"] == "进阶"
    assert item["duration_minutes"] == 45


def test_list_v2_sessions_in_progress_when_active() -> None:
    headers = _auth_headers()
    session_id = _create_confirmed_session(headers)
    client.post(f"/api/interviews/{session_id}/activate", headers=headers)

    item = _find_session(client.get("/api/interviews", headers=headers).json(), session_id)
    assert item["status"] == "active"
    assert item["display_label"] == "in_progress"
    assert item["action_label"] == "继续面试"
    assert item["remaining_seconds"] is not None
    assert item["remaining_seconds"] > 0


def test_list_v2_sessions_evaluating_after_finish() -> None:
    headers = _auth_headers()
    session_id = _create_confirmed_session(headers)
    client.post(f"/api/interviews/{session_id}/activate", headers=headers)
    client.post(f"/api/interviews/{session_id}/finish", headers=headers)

    item = _find_session(client.get("/api/interviews", headers=headers).json(), session_id)
    assert item["status"] == "evaluating"
    assert item["display_label"] == "evaluating"
    assert item["action_label"] == "查看评估报告"
    assert item["action_path"].endswith("/evaluation")


def test_list_v2_sessions_reconciles_stale_active() -> None:
    headers = _auth_headers()
    session_id = _create_confirmed_session(headers)
    user_id = client.get("/api/auth/me", headers=headers).json()["id"]
    client.post(f"/api/interviews/{session_id}/activate", headers=headers)

    store = Store()
    record = store.get_interview_session_record(user_id, session_id)
    runtime_state = dict(record["workflow_state"])
    runtime_state["deadline_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    store.update_session(session_id, workflow_state=runtime_state)

    item = _find_session(client.get("/api/interviews", headers=headers).json(), session_id)
    assert item["status"] == "evaluating"
    assert item["display_label"] == "pending_evaluation"
    assert item["action_label"] == "生成评估报告"
