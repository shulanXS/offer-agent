import uuid

from fastapi.testclient import TestClient

from app.db.store import Store
from app.main import app


client = TestClient(app)


def _auth_headers() -> dict[str, str]:
    username = f"eval_{uuid.uuid4().hex[:8]}"
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


def test_evaluate_completes_session_and_returns_minimal_report() -> None:
    headers = _auth_headers()
    session_id = _create_confirmed_session(headers)

    client.post(f"/api/interviews/{session_id}/activate", headers=headers)
    finished = client.post(f"/api/interviews/{session_id}/finish", headers=headers)
    assert finished.status_code == 200
    assert finished.json()["status"] == "evaluating"

    before = client.get(f"/api/interviews/{session_id}/evaluation", headers=headers)
    assert before.status_code == 200
    assert before.json() is None

    evaluated = client.post(f"/api/interviews/{session_id}/evaluate", headers=headers)
    assert evaluated.status_code == 200
    payload = evaluated.json()
    assert payload["status"] == "completed"
    assert payload["evaluation"]["source"] in {"evidence_rule", "agent_enriched", "rule_minimal"}
    assert "summary" in payload["evaluation"]
    assert "coverage_rate" in payload["evaluation"]
    assert "competencies" in payload["evaluation"]
    assert isinstance(payload["evaluation"]["competencies"], list)
    assert payload["evaluation"]["jd_match"] is None
    assert isinstance(payload["evaluation"]["risks"], list)
    assert isinstance(payload["evaluation"]["unverified_items"], list)

    fetched = client.get(f"/api/interviews/{session_id}/evaluation", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["evaluation"]["summary"] == payload["evaluation"]["summary"]

    replay = client.post(f"/api/interviews/{session_id}/evaluate", headers=headers)
    assert replay.status_code == 200
    assert replay.json()["evaluation"]["summary"] == payload["evaluation"]["summary"]


def test_evaluate_rejects_active_session() -> None:
    headers = _auth_headers()
    session_id = _create_confirmed_session(headers)
    client.post(f"/api/interviews/{session_id}/activate", headers=headers)

    response = client.post(f"/api/interviews/{session_id}/evaluate", headers=headers)
    assert response.status_code == 409
