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


def _detailed_answer(topic_name: str) -> str:
    return (
        f"关于{topic_name}，我负责核心模块设计、开发、上线与结果验证，"
        "通过指标监控和灰度发布确保稳定性，并沉淀了可复用方案。"
    )


def test_activate_sets_deadline_and_remaining_seconds() -> None:
    headers = _auth_headers()
    session_id, _ = _create_confirmed_session(headers)

    activated = client.post(f"/api/interviews/{session_id}/activate", headers=headers)
    assert activated.status_code == 200
    progress = activated.json()["progress"]
    assert progress["remaining_seconds"] == 45 * 60
    assert not progress["deadline_at"]
    assert progress["max_answer_rounds"] == 12

    detail = client.get(f"/api/interviews/{session_id}", headers=headers)
    assert detail.status_code == 200
    live_progress = detail.json()["progress"]
    assert live_progress["deadline_at"]
    assert live_progress["remaining_seconds"] is not None
    assert live_progress["remaining_seconds"] > 40 * 60


def test_max_answer_rounds_forces_finish(monkeypatch) -> None:
    monkeypatch.setattr("app.services.interview.boundaries.MAX_ANSWER_ROUNDS", 2)

    headers = _auth_headers()
    session_id, plan_json = _create_confirmed_session(headers)
    first_topic = plan_json["topics"][0]

    client.post(f"/api/interviews/{session_id}/activate", headers=headers)
    client.post(
        f"/api/interviews/{session_id}/reply/stream",
        headers=headers,
        json={"content": _detailed_answer(first_topic["name"])},
    )

    client.post(
        f"/api/interviews/{session_id}/reply/stream",
        headers=headers,
        json={"content": _detailed_answer(first_topic["name"])},
    )

    detail = client.get(f"/api/interviews/{session_id}", headers=headers).json()
    assert detail["status"] == "evaluating"
    assert detail["progress"]["answer_round"] == 2
    assistant_messages = [item for item in detail["messages"] if item["role"] == "assistant"]
    assert assistant_messages[-1]["meta"]["action"] == "finish"


def test_past_deadline_forces_finish() -> None:
    headers = _auth_headers()
    session_id, plan_json = _create_confirmed_session(headers)
    first_topic = plan_json["topics"][0]

    client.post(f"/api/interviews/{session_id}/activate", headers=headers)

    store = Store()
    record = store.get_interview_session_record(
        client.get("/api/auth/me", headers=headers).json()["id"],
        session_id,
    )
    runtime_state = dict(record["workflow_state"])
    runtime_state["deadline_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    store.update_session(session_id, workflow_state=runtime_state)

    client.post(
        f"/api/interviews/{session_id}/reply/stream",
        headers=headers,
        json={"content": _detailed_answer(first_topic["name"])},
    )

    detail = client.get(f"/api/interviews/{session_id}", headers=headers).json()
    assert detail["status"] == "evaluating"
    assert "时间" in detail["messages"][-1]["content"] or "结束" in detail["messages"][-1]["content"]


def test_user_finish_interview() -> None:
    headers = _auth_headers()
    session_id, _ = _create_confirmed_session(headers)

    client.post(f"/api/interviews/{session_id}/activate", headers=headers)
    finished = client.post(f"/api/interviews/{session_id}/finish", headers=headers)
    assert finished.status_code == 200
    payload = finished.json()
    assert payload["status"] == "evaluating"
    assert "主动结束" in payload["messages"][-1]["content"]

    blocked = client.post(
        f"/api/interviews/{session_id}/reply/stream",
        headers=headers,
        json={"content": "不应再接受回答"},
    )
    assert blocked.status_code == 409


def test_finished_remaining_seconds_frozen() -> None:
    headers = _auth_headers()
    session_id, _ = _create_confirmed_session(headers)
    user_id = client.get("/api/auth/me", headers=headers).json()["id"]

    client.post(f"/api/interviews/{session_id}/activate", headers=headers)
    finished = client.post(f"/api/interviews/{session_id}/finish", headers=headers).json()
    frozen = finished["progress"]["remaining_seconds"]
    assert frozen is not None
    assert frozen > 0

    record = Store().get_interview_session_record(user_id, session_id)
    assert record["workflow_state"].get("remaining_seconds_at_finish") == frozen

    detail = client.get(f"/api/interviews/{session_id}", headers=headers).json()
    assert detail["progress"]["remaining_seconds"] == frozen


def test_duplicate_reply_rejected() -> None:
    headers = _auth_headers()
    session_id, _ = _create_confirmed_session(headers)
    user_id = client.get("/api/auth/me", headers=headers).json()["id"]

    client.post(f"/api/interviews/{session_id}/activate", headers=headers)

    store = Store()
    record = store.get_interview_session_record(user_id, session_id)
    runtime_state = dict(record["workflow_state"])
    current_topic_id = str(runtime_state.get("current_topic_id", ""))
    store.create_message(
        session_id=session_id,
        role="user",
        kind="answer",
        content="正在处理中的回答",
        meta={"topic_id": current_topic_id},
    )
    runtime_state["reply_in_progress"] = True
    store.update_session(session_id, workflow_state=runtime_state)

    blocked = client.post(
        f"/api/interviews/{session_id}/reply/stream",
        headers=headers,
        json={"content": "并发回答"},
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "INTERVIEW_REPLY_IN_PROGRESS"


def test_topic_probe_limit_advances(monkeypatch) -> None:
    monkeypatch.setattr("app.services.interview.boundaries.MAX_TOPIC_PROBE_COUNT", 1)

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


def test_get_session_clears_stale_reply_lock(monkeypatch) -> None:
    monkeypatch.setattr("app.core.config.settings.interview_stale_reply_lock_seconds", 0)

    headers = _auth_headers()
    session_id, _ = _create_confirmed_session(headers)
    user_id = client.get("/api/auth/me", headers=headers).json()["id"]

    client.post(f"/api/interviews/{session_id}/activate", headers=headers)

    store = Store()
    record = store.get_interview_session_record(user_id, session_id)
    runtime_state = dict(record["workflow_state"])
    runtime_state["reply_in_progress"] = True
    store.update_session(session_id, workflow_state=runtime_state)

    detail = client.get(f"/api/interviews/{session_id}", headers=headers).json()
    assert detail["progress"]["is_reply_processing"] is False


def test_get_session_clears_reply_lock_when_assistant_already_replied() -> None:
    headers = _auth_headers()
    session_id, _ = _create_confirmed_session(headers)
    user_id = client.get("/api/auth/me", headers=headers).json()["id"]

    client.post(f"/api/interviews/{session_id}/activate", headers=headers)
    client.post(
        f"/api/interviews/{session_id}/reply/stream",
        headers=headers,
        json={"content": "我负责订单系统后端开发，使用 Java 和 Spring。"},
    )

    store = Store()
    record = store.get_interview_session_record(user_id, session_id)
    runtime_state = dict(record["workflow_state"])
    runtime_state["reply_in_progress"] = True
    store.update_session(session_id, workflow_state=runtime_state)

    detail = client.get(f"/api/interviews/{session_id}", headers=headers).json()
    assert detail["progress"]["is_reply_processing"] is False
    assert detail["messages"][-1]["role"] == "assistant"
