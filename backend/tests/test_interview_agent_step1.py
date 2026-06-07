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


def test_activate_requires_confirmed_plan() -> None:
    headers = _auth_headers()
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
    blocked = client.post(f"/api/interviews/{created['session_id']}/activate", headers=headers)
    assert blocked.status_code == 409


def test_activate_opens_first_topic_from_plan() -> None:
    headers = _auth_headers()
    session_id, plan_json = _create_confirmed_session(headers)
    first_topic = plan_json["topics"][0]

    activated = client.post(f"/api/interviews/{session_id}/activate", headers=headers)
    assert activated.status_code == 200
    payload = activated.json()
    assert payload["status"] == "active"
    assert payload["progress"]["current_topic_id"] == first_topic["id"]
    assert payload["progress"]["completed_topic_count"] == 0
    assert len(payload["messages"]) == 1
    assert payload["messages"][0]["meta"]["topic_id"] == first_topic["id"]
    assert payload["messages"][0]["meta"]["action"] == "opening"
    assert first_topic["opening_question"][:8] in payload["messages"][0]["content"]


def test_activate_is_idempotent_and_does_not_duplicate_opening() -> None:
    headers = _auth_headers()
    session_id, _plan_json = _create_confirmed_session(headers)

    first = client.post(f"/api/interviews/{session_id}/activate", headers=headers)
    second = client.post(f"/api/interviews/{session_id}/activate", headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200

    detail = client.get(f"/api/interviews/{session_id}", headers=headers).json()
    opening_messages = [item for item in detail["messages"] if item.get("meta", {}).get("action") == "opening"]
    assert len(opening_messages) == 1


def _detailed_answer(topic_name: str) -> str:
    return (
        f"关于{topic_name}，我负责核心模块设计、开发、上线与结果验证，"
        "通过指标监控和灰度发布确保稳定性，并沉淀了可复用方案。"
    )


def test_step1_fixed_topic_flow_and_consistency() -> None:
    headers = _auth_headers()
    session_id, plan_json = _create_confirmed_session(headers)
    topics = plan_json["topics"]

    client.post(f"/api/interviews/{session_id}/activate", headers=headers)

    for index, topic in enumerate(topics):
        detail = client.get(f"/api/interviews/{session_id}", headers=headers).json()
        assert detail["status"] == "active" or (index == len(topics) - 1 and detail["status"] == "evaluating")
        if detail["status"] == "evaluating":
            break
        assert detail["progress"]["current_topic_id"] == topic["id"]

        reply = client.post(
            f"/api/interviews/{session_id}/reply/stream",
            headers=headers,
            json={"content": _detailed_answer(topic["name"])},
        )
        assert reply.status_code == 200

        detail = client.get(f"/api/interviews/{session_id}", headers=headers).json()
        user_messages = [item for item in detail["messages"] if item["role"] == "user"]
        assert user_messages[-1]["meta"]["topic_id"] == topic["id"]

        if index < len(topics) - 1:
            assert detail["status"] == "active"
            next_topic = topics[index + 1]
            assistant_messages = [item for item in detail["messages"] if item["role"] == "assistant"]
            assert assistant_messages[-1]["meta"]["topic_id"] == next_topic["id"]
            assert assistant_messages[-1]["meta"]["action"] == "next_topic"
            assert next_topic["opening_question"][:8] in assistant_messages[-1]["content"]
        else:
            assert detail["status"] == "evaluating"
            assert detail["progress"]["completed_topic_count"] == len(topics)


def test_evaluating_session_rejects_reply() -> None:
    headers = _auth_headers()
    session_id, plan_json = _create_confirmed_session(headers)
    client.post(f"/api/interviews/{session_id}/activate", headers=headers)
    for topic in plan_json["topics"]:
        client.post(
            f"/api/interviews/{session_id}/reply/stream",
            headers=headers,
            json={"content": _detailed_answer(topic["name"])},
        )

    blocked = client.post(
        f"/api/interviews/{session_id}/reply/stream",
        headers=headers,
        json={"content": "不应再接受回答"},
    )
    assert blocked.status_code == 409


def test_vague_answer_triggers_follow_up() -> None:
    headers = _auth_headers()
    session_id, plan_json = _create_confirmed_session(headers)
    first_topic = plan_json["topics"][0]

    client.post(f"/api/interviews/{session_id}/activate", headers=headers)
    client.post(
        f"/api/interviews/{session_id}/reply/stream",
        headers=headers,
        json={"content": "做过一些相关 work。"},
    )

    detail = client.get(f"/api/interviews/{session_id}", headers=headers).json()
    assert detail["status"] == "active"
    assert detail["progress"]["current_topic_id"] == first_topic["id"]
    assert detail["progress"]["phase"] == "topic_follow_up"

    assistant_messages = [item for item in detail["messages"] if item["role"] == "assistant"]
    follow_up = assistant_messages[-1]
    assert follow_up["meta"]["topic_id"] == first_topic["id"]
    assert follow_up["meta"]["is_follow_up"] is True
    assert str(follow_up["meta"]["action"]).startswith("probe_")


def test_sufficient_answer_advances_topic() -> None:
    headers = _auth_headers()
    session_id, plan_json = _create_confirmed_session(headers)
    first_topic = plan_json["topics"][0]
    second_topic = plan_json["topics"][1]

    client.post(f"/api/interviews/{session_id}/activate", headers=headers)
    client.post(
        f"/api/interviews/{session_id}/reply/stream",
        headers=headers,
        json={"content": _detailed_answer(first_topic["name"])},
    )

    detail = client.get(f"/api/interviews/{session_id}", headers=headers).json()
    assert detail["progress"]["current_topic_id"] == second_topic["id"]
    assistant_messages = [item for item in detail["messages"] if item["role"] == "assistant"]
    assert assistant_messages[-1]["meta"]["action"] == "next_topic"
