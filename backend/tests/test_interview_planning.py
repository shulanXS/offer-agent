from fastapi.testclient import TestClient

from app.db.store import Store
from app.main import app


client = TestClient(app)


def _auth_headers() -> dict[str, str]:
    username = "planning_user"
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


def test_create_interview_rejects_invalid_configuration() -> None:
    headers = _auth_headers()
    resume_id = _create_ready_resume(headers)

    response = client.post(
        "/api/interviews",
        headers=headers,
        json={
            "resume_id": resume_id,
            "interview_type": "experienced",
            "target_role": "backend",
            "language": "java",
            "target_level": "intermediate",
            "duration_minutes": 30,
            "focus_topics": ["项目深挖"],
            "jd_text": "",
        },
    )

    assert response.status_code == 400
    assert response.json()["code"] == "INTERVIEW_CONFIG_INVALID"


def test_create_interview_returns_plan_preview() -> None:
    headers = _auth_headers()
    resume_id = _create_ready_resume(headers)

    response = client.post(
        "/api/interviews",
        headers=headers,
        json={
            "resume_id": resume_id,
            "interview_type": "experienced",
            "target_role": "backend",
            "language": "java",
            "target_level": "intermediate",
            "duration_minutes": 45,
            "focus_topics": ["项目深挖", "系统设计"],
            "jd_text": "负责高并发订单系统",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "plan_ready"
    assert payload["plan_version"] == 1
    assert len(payload["topics_preview"]) >= 5
    assert payload["candidate_summary"]["has_jd"] is True
    assert payload["candidate_summary"]["interview_type_label"] == "社招"
    assert all("opening_question" not in topic for topic in payload["topics_preview"])

    detail = client.get(f"/api/interviews/{payload['session_id']}", headers=headers).json()
    assert detail["plan"]["plan_id"] == payload["plan_id"]


def test_create_interview_campus_and_experienced_differ() -> None:
    headers = _auth_headers()
    resume_id = _create_ready_resume(headers)

    experienced = client.post(
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
    campus = client.post(
        "/api/interviews",
        headers=headers,
        json={
            "resume_id": resume_id,
            "interview_type": "campus",
            "target_role": "backend",
            "language": "python",
            "target_level": "beginner",
            "duration_minutes": 45,
            "focus_topics": ["学习能力"],
            "jd_text": "",
        },
    ).json()

    experienced_names = [topic["name"] for topic in experienced["topics_preview"]]
    campus_names = [topic["name"] for topic in campus["topics_preview"]]
    assert experienced_names != campus_names


def test_create_interview_with_jd_reference_summary_mentions_jd() -> None:
    headers = _auth_headers()
    resume_id = _create_ready_resume(headers)

    payload = client.post(
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
            "jd_text": "负责高并发订单系统与性能优化",
        },
    ).json()

    joined = " ".join(payload["candidate_summary"]["reference_summary"])
    assert "JD" in joined or "高并发" in joined


def test_plan_generate_is_idempotent_when_plan_ready() -> None:
    headers = _auth_headers()
    resume_id = _create_ready_resume(headers)

    created = client.post(
        "/api/interviews",
        headers=headers,
        json={
            "resume_id": resume_id,
            "interview_type": "campus",
            "target_role": "backend",
            "language": "python",
            "target_level": "beginner",
            "duration_minutes": 45,
            "focus_topics": ["学习能力"],
            "jd_text": "",
        },
    ).json()

    regenerated = client.post(
        f"/api/interviews/{created['session_id']}/plan/generate",
        headers=headers,
    ).json()

    assert regenerated["plan_id"] == created["plan_id"]
    assert regenerated["candidate_summary"]["interview_type_label"] == "校招"


def _create_interview(headers: dict[str, str], resume_id: str, *, focus_topics: list[str] | None = None) -> dict:
    return client.post(
        "/api/interviews",
        headers=headers,
        json={
            "resume_id": resume_id,
            "interview_type": "experienced",
            "target_role": "backend",
            "language": "java",
            "target_level": "intermediate",
            "duration_minutes": 45,
            "focus_topics": focus_topics or ["项目深挖", "系统设计"],
            "jd_text": "",
        },
    ).json()


def test_regenerate_plan_creates_new_version() -> None:
    headers = _auth_headers()
    resume_id = _create_ready_resume(headers)
    created = _create_interview(headers, resume_id)

    regenerated = client.post(
        f"/api/interviews/{created['session_id']}/plan/regenerate",
        headers=headers,
        json={
            "regeneration_strategy": "increase_technical_depth",
            "additional_instruction": "",
        },
    ).json()

    assert regenerated["plan_version"] == 2
    assert regenerated["plan_id"] != created["plan_id"]
    assert regenerated["regenerations_remaining"] == 1
    assert regenerated["candidate_summary"]["reference_summary"] != created["candidate_summary"]["reference_summary"]

    detail = client.get(f"/api/interviews/{created['session_id']}", headers=headers).json()
    assert len(detail["version_history"]) == 2


def test_regenerate_rejects_align_jd_without_jd() -> None:
    headers = _auth_headers()
    resume_id = _create_ready_resume(headers)
    created = _create_interview(headers, resume_id)

    response = client.post(
        f"/api/interviews/{created['session_id']}/plan/regenerate",
        headers=headers,
        json={
            "regeneration_strategy": "align_jd",
            "focus_topics": [],
            "additional_instruction": "",
        },
    )

    assert response.status_code == 400


def test_regenerate_limit_enforced_by_backend() -> None:
    headers = _auth_headers()
    resume_id = _create_ready_resume(headers)
    created = _create_interview(headers, resume_id)
    session_id = created["session_id"]

    strategies = [
        "increase_technical_depth",
        "increase_fundamentals",
    ]
    latest = created
    for strategy in strategies:
        latest = client.post(
            f"/api/interviews/{session_id}/plan/regenerate",
            headers=headers,
            json={"regeneration_strategy": strategy, "additional_instruction": ""},
        ).json()

    assert latest["plan_version"] == 3
    assert latest["regenerations_remaining"] == 0

    blocked = client.post(
        f"/api/interviews/{session_id}/plan/regenerate",
        headers=headers,
        json={"regeneration_strategy": "align_resume", "focus_topics": [], "additional_instruction": ""},
    )
    assert blocked.status_code == 429


def test_confirm_plan_locks_session() -> None:
    headers = _auth_headers()
    resume_id = _create_ready_resume(headers)
    created = _create_interview(headers, resume_id)
    session_id = created["session_id"]

    confirmed = client.post(f"/api/interviews/{session_id}/plan/confirm", headers=headers).json()

    assert confirmed["status"] == "plan_confirmed"
    assert confirmed["plan_id"] == created["plan_id"]
    assert confirmed["regenerations_remaining"] == 0

    detail = client.get(f"/api/interviews/{session_id}", headers=headers).json()
    assert detail["status"] == "plan_confirmed"
    assert detail["confirmed_plan_id"] == created["plan_id"]
    assert detail["plan"]["plan_id"] == created["plan_id"]


def test_confirm_plan_blocks_regenerate() -> None:
    headers = _auth_headers()
    resume_id = _create_ready_resume(headers)
    created = _create_interview(headers, resume_id)
    session_id = created["session_id"]

    client.post(f"/api/interviews/{session_id}/plan/confirm", headers=headers)

    blocked = client.post(
        f"/api/interviews/{session_id}/plan/regenerate",
        headers=headers,
        json={"regeneration_strategy": "align_resume", "focus_topics": [], "additional_instruction": ""},
    )
    assert blocked.status_code == 409


def test_confirm_plan_rejects_duplicate() -> None:
    headers = _auth_headers()
    resume_id = _create_ready_resume(headers)
    created = _create_interview(headers, resume_id)
    session_id = created["session_id"]

    client.post(f"/api/interviews/{session_id}/plan/confirm", headers=headers)
    duplicate = client.post(f"/api/interviews/{session_id}/plan/confirm", headers=headers)

    assert duplicate.status_code == 409
