from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
import uuid

from app.db.store import Store
from app.main import app


client = TestClient(app)


def _auth_headers() -> dict[str, str]:
    username = f"live_{uuid.uuid4().hex[:8]}"
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
            "resume_text": "姓名：张三\n熟悉 Java 和后端开发，参与订单系统项目。",
            "work_experience": [{"name": "某科技公司", "detail": "负责订单系统后端开发"}],
            "project_experience": [{"name": "订单系统", "detail": "高并发订单处理"}],
            "model_provider": "openai",
            "model_name": "",
        },
    )
    return resume["id"]


def _create_confirmed_session(headers: dict[str, str]) -> tuple[str, dict]:
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
    store = Store()
    plan = store.get_plan_by_id(created["plan_id"])
    return session_id, plan["plan_json"]


def _patch_runtime_state(headers: dict[str, str], session_id: str, **updates) -> dict:
    store = Store()
    user_id = client.get("/api/auth/me", headers=headers).json()["id"]
    record = store.get_interview_session_record(user_id, session_id)
    runtime_state = dict(record["workflow_state"])
    runtime_state.update(updates)
    store.update_session(session_id, workflow_state=runtime_state)
    return runtime_state


def test_topic_answer_round_limit_forces_advance(monkeypatch) -> None:
    monkeypatch.setattr("app.services.interview.boundaries.MAX_TOPIC_PROBE_COUNT", 99)
    monkeypatch.setattr("app.services.interview.boundaries.MAX_TOPIC_ANSWER_ROUNDS", 2)

    headers = _auth_headers()
    session_id, plan_json = _create_confirmed_session(headers)
    first_topic = plan_json["topics"][0]
    second_topic = plan_json["topics"][1]

    client.post(f"/api/interviews/{session_id}/activate", headers=headers)
    client.post(
        f"/api/interviews/{session_id}/reply/stream",
        headers=headers,
        json={"content": "简短回答。"},
    )
    client.post(
        f"/api/interviews/{session_id}/reply/stream",
        headers=headers,
        json={"content": "仍然很简短。"},
    )

    detail = client.get(f"/api/interviews/{session_id}", headers=headers).json()
    assert detail["status"] == "active"
    assert detail["progress"]["current_topic_id"] == second_topic["id"]
    assert detail["progress"]["current_topic_id"] != first_topic["id"]


def test_repeat_probe_blocked_advances_topic(monkeypatch) -> None:
    monkeypatch.setattr("app.services.interview.boundaries.MAX_TOPIC_PROBE_COUNT", 5)
    monkeypatch.setattr("app.services.interview.boundaries.MAX_TOPIC_ANSWER_ROUNDS", 5)

    headers = _auth_headers()
    session_id, plan_json = _create_confirmed_session(headers)
    first_topic = plan_json["topics"][0]
    second_topic = plan_json["topics"][1]

    client.post(f"/api/interviews/{session_id}/activate", headers=headers)
    client.post(
        f"/api/interviews/{session_id}/reply/stream",
        headers=headers,
        json={"content": "简短回答。"},
    )
    client.post(
        f"/api/interviews/{session_id}/reply/stream",
        headers=headers,
        json={"content": "还是简短。"},
    )

    detail = client.get(f"/api/interviews/{session_id}", headers=headers).json()
    assert detail["status"] == "active"
    assert detail["progress"]["current_topic_id"] == second_topic["id"]
    assistant_messages = [item for item in detail["messages"] if item["role"] == "assistant"]
    assert assistant_messages[-1]["meta"]["topic_id"] == second_topic["id"]
    assert assistant_messages[-1]["meta"]["action"] == "next_topic"
    assert detail["progress"]["completed_topic_count"] == 1


def test_wrap_up_zone_advances_when_required_topics_not_covered() -> None:
    headers = _auth_headers()
    session_id, plan_json = _create_confirmed_session(headers)
    first_topic = plan_json["topics"][0]
    second_topic = plan_json["topics"][1]

    client.post(f"/api/interviews/{session_id}/activate", headers=headers)
    _patch_runtime_state(
        headers,
        session_id,
        deadline_at=(datetime.now(timezone.utc) + timedelta(minutes=4)).isoformat(),
        completed_topic_ids=[],
    )

    client.post(
        f"/api/interviews/{session_id}/reply/stream",
        headers=headers,
        json={"content": "关于该主题我有一些实践经验，但还需要补充更多细节。"},
    )

    detail = client.get(f"/api/interviews/{session_id}", headers=headers).json()
    assert detail["status"] == "active"
    assert detail["progress"]["is_wrap_up_zone"] is True
    assert detail["progress"]["current_topic_id"] == second_topic["id"]
    assert detail["progress"]["current_topic_id"] != first_topic["id"]


def test_wrap_up_zone_finishes_when_required_topics_covered() -> None:
    headers = _auth_headers()
    session_id, plan_json = _create_confirmed_session(headers)
    required_ids = [str(topic["id"]) for topic in plan_json["topics"] if topic.get("required", True)]

    client.post(f"/api/interviews/{session_id}/activate", headers=headers)
    _patch_runtime_state(
        headers,
        session_id,
        deadline_at=(datetime.now(timezone.utc) + timedelta(minutes=4)).isoformat(),
        completed_topic_ids=required_ids,
    )

    client.post(
        f"/api/interviews/{session_id}/reply/stream",
        headers=headers,
        json={"content": "补充最后一点说明。"},
    )

    detail = client.get(f"/api/interviews/{session_id}", headers=headers).json()
    assert detail["status"] == "evaluating"
    assert detail["progress"]["is_wrap_up_zone"] is True
    assert detail["messages"][-1]["meta"]["action"] == "finish"
