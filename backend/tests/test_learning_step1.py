import uuid

from fastapi.testclient import TestClient

from app.db.store import Store
from app.main import app
from app.services.learning.aggregate import aggregate_profile, build_outcome_snapshot


client = TestClient(app)


def _auth_headers() -> dict[str, str]:
    username = f"learn_{uuid.uuid4().hex[:8]}"
    password = "password123"
    register_response = client.post("/api/auth/register", json={"username": username, "password": password})
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


def _create_confirmed_session(headers: dict[str, str], *, resume_id: str | None = None) -> str:
    resume_id = resume_id or _create_ready_resume(headers)
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


def _complete_session(headers: dict[str, str], session_id: str) -> dict:
    client.post(f"/api/interviews/{session_id}/activate", headers=headers)
    client.post(f"/api/interviews/{session_id}/finish", headers=headers)
    evaluated = client.post(f"/api/interviews/{session_id}/evaluate", headers=headers)
    assert evaluated.status_code == 200
    return evaluated.json()


def test_aggregate_repeat_weak_signals() -> None:
    plan_json = {
        "topics": [
            {
                "id": "topic-1",
                "name": "项目深挖",
                "dimension": "项目经历",
                "expected_signals": ["个人贡献", "结果指标"],
            }
        ]
    }
    outcome_one = build_outcome_snapshot(
        session_id="s1",
        completed_at="2026-06-01T00:00:00+00:00",
        plan_json=plan_json,
        evaluation={
            "competencies": [
                {
                    "topic_id": "topic-1",
                    "name": "项目深挖",
                    "dimension": "项目经历",
                    "status": "partially_verified",
                    "score": 3,
                }
            ]
        },
        evidence_by_topic={
            "topic-1": {"missing_signals": ["结果指标"], "covered_signals": ["个人贡献"], "evidence": []},
        },
    )
    outcome_two = build_outcome_snapshot(
        session_id="s2",
        completed_at="2026-06-02T00:00:00+00:00",
        plan_json=plan_json,
        evaluation={
            "competencies": [
                {
                    "topic_id": "topic-1",
                    "name": "项目深挖",
                    "dimension": "项目经历",
                    "status": "partially_verified",
                    "score": 3,
                }
            ]
        },
        evidence_by_topic={
            "topic-1": {"missing_signals": ["结果指标"], "covered_signals": [], "evidence": []},
        },
    )
    profile = aggregate_profile([outcome_one, outcome_two])
    assert profile["session_count"] == 2
    assert profile["repeat_weak_signals"]
    assert profile["repeat_weak_signals"][0]["signal"] == "结果指标"
    assert profile["repeat_weak_signals"][0]["count"] == 2
    assert profile["repeat_weak_signals"][0]["suggested_focus_topic"] in {
        "项目深挖",
        "技术基础",
        "业务理解",
        "问题排查",
        "沟通表达",
        "学习能力",
        "算法与编码",
        "Agent 工程能力",
        "Prompt 设计",
        "系统设计",
    }


def test_record_session_outcome_after_evaluate() -> None:
    headers = _auth_headers()
    resume_id = _create_ready_resume(headers)
    session_id = _create_confirmed_session(headers, resume_id=resume_id)
    _complete_session(headers, session_id)

    context = client.get(f"/api/interviews/{session_id}/learning-context", headers=headers)
    assert context.status_code == 200
    payload = context.json()
    assert payload["has_learning_profile"] is True
    assert payload["session_count"] == 1
    assert payload["cross_session_available"] is False

    recommendations = client.get(
        "/api/users/me/learning-recommendations",
        headers=headers,
        params={
            "resume_id": resume_id,
            "target_role": "backend",
            "interview_type": "experienced",
        },
    )
    assert recommendations.status_code == 200
    rec = recommendations.json()
    assert rec["has_learning_profile"] is True
    assert rec["recommendations_available"] is False


def test_improved_signals_ignore_undiscussed_topics() -> None:
    plan_json = {
        "topics": [
            {
                "id": "topic-1",
                "name": "项目深挖",
                "dimension": "项目经历",
                "expected_signals": ["个人贡献", "结果指标"],
            },
            {
                "id": "topic-2",
                "name": "技术基础",
                "dimension": "技术深度",
                "expected_signals": ["设计模式理解"],
            },
        ]
    }
    outcome_one = build_outcome_snapshot(
        session_id="s1",
        completed_at="2026-06-01T00:00:00+00:00",
        plan_json=plan_json,
        evaluation={
            "competencies": [
                {
                    "topic_id": "topic-1",
                    "name": "项目深挖",
                    "dimension": "项目经历",
                    "status": "partially_verified",
                    "score": 3,
                },
                {
                    "topic_id": "topic-2",
                    "name": "技术基础",
                    "dimension": "技术深度",
                    "status": "unverified",
                    "score": None,
                },
            ]
        },
        evidence_by_topic={
            "topic-1": {
                "missing_signals": ["结果指标"],
                "covered_signals": ["个人贡献"],
                "evidence": [{"quote": "负责订单系统"}],
            },
            "topic-2": {
                "missing_signals": ["设计模式理解"],
                "covered_signals": [],
                "evidence": [],
            },
        },
    )
    outcome_two = build_outcome_snapshot(
        session_id="s2",
        completed_at="2026-06-02T00:00:00+00:00",
        plan_json=plan_json,
        evaluation={
            "competencies": [
                {
                    "topic_id": "topic-1",
                    "name": "项目深挖",
                    "dimension": "项目经历",
                    "status": "partially_verified",
                    "score": 4,
                },
                {
                    "topic_id": "topic-2",
                    "name": "技术基础",
                    "dimension": "技术深度",
                    "status": "unverified",
                    "score": None,
                },
            ]
        },
        evidence_by_topic={
            "topic-1": {
                "missing_signals": [],
                "covered_signals": ["个人贡献", "结果指标"],
                "evidence": [{"quote": "订单系统 QPS 提升 30%"}],
            },
            "topic-2": {
                "missing_signals": ["设计模式理解"],
                "covered_signals": [],
                "evidence": [],
            },
        },
    )

    profile = aggregate_profile([outcome_one, outcome_two])
    improved = profile["improved_signals"]
    assert len(improved) == 1
    assert improved[0]["topic_dimension"] == "项目经历"
    assert improved[0]["signals"] == ["结果指标"]
    assert improved[0]["status_label"] == "本轮已覆盖"
    assert all("设计模式理解" not in group["signals"] for group in improved)


def test_improved_signals_require_latest_rediscussed_dimension() -> None:
    plan_json = {
        "topics": [
            {
                "id": "topic-1",
                "name": "项目深挖",
                "dimension": "项目经历",
                "expected_signals": ["结果指标"],
            },
            {
                "id": "topic-2",
                "name": "技术基础",
                "dimension": "技术深度",
                "expected_signals": ["设计模式理解"],
            },
        ]
    }
    outcome_one = build_outcome_snapshot(
        session_id="s1",
        completed_at="2026-06-01T00:00:00+00:00",
        plan_json=plan_json,
        evaluation={
            "competencies": [
                {
                    "topic_id": "topic-1",
                    "name": "项目深挖",
                    "dimension": "项目经历",
                    "status": "partially_verified",
                    "score": 3,
                },
                {
                    "topic_id": "topic-2",
                    "name": "技术基础",
                    "dimension": "技术深度",
                    "status": "unverified",
                    "score": None,
                },
            ]
        },
        evidence_by_topic={
            "topic-1": {
                "missing_signals": ["结果指标"],
                "covered_signals": [],
                "evidence": [{"quote": "项目经历"}],
            },
            "topic-2": {
                "missing_signals": ["设计模式理解"],
                "covered_signals": [],
                "evidence": [],
            },
        },
    )
    outcome_two = build_outcome_snapshot(
        session_id="s2",
        completed_at="2026-06-02T00:00:00+00:00",
        plan_json={
            "topics": [
                {
                    "id": "topic-9",
                    "name": "系统设计",
                    "dimension": "方案取舍或系统设计",
                    "expected_signals": ["架构视角"],
                }
            ]
        },
        evaluation={
            "competencies": [
                {
                    "topic_id": "topic-9",
                    "name": "系统设计",
                    "dimension": "方案取舍或系统设计",
                    "status": "partially_verified",
                    "score": 3,
                }
            ]
        },
        evidence_by_topic={
            "topic-9": {
                "missing_signals": ["架构视角"],
                "covered_signals": [],
                "evidence": [{"quote": "微服务拆分"}],
            }
        },
    )

    profile = aggregate_profile([outcome_one, outcome_two])
    assert profile["improved_signals"] == []


def test_improved_signals_merge_by_dimension_and_limit_groups() -> None:
    plan_json = {
        "topics": [
            {
                "id": "topic-1",
                "name": "项目深挖",
                "dimension": "项目经历",
                "expected_signals": ["信号A", "信号B", "信号C", "信号D", "信号E", "信号F"],
            }
        ]
    }
    base_competency = {
        "topic_id": "topic-1",
        "name": "项目深挖",
        "dimension": "项目经历",
        "status": "partially_verified",
        "score": 3,
    }
    prior_missing = ["信号A", "信号B", "信号C", "信号D", "信号E", "信号F"]
    outcome_one = build_outcome_snapshot(
        session_id="s1",
        completed_at="2026-06-01T00:00:00+00:00",
        plan_json=plan_json,
        evaluation={"competencies": [base_competency]},
        evidence_by_topic={
            "topic-1": {
                "missing_signals": prior_missing,
                "covered_signals": [],
                "evidence": [{"quote": "回答1"}],
            }
        },
    )
    outcome_two = build_outcome_snapshot(
        session_id="s2",
        completed_at="2026-06-02T00:00:00+00:00",
        plan_json=plan_json,
        evaluation={"competencies": [base_competency]},
        evidence_by_topic={
            "topic-1": {
                "missing_signals": [],
                "covered_signals": prior_missing,
                "evidence": [{"quote": "回答2"}],
            }
        },
    )

    profile = aggregate_profile([outcome_one, outcome_two])
    improved = profile["improved_signals"]
    assert len(improved) == 1
    assert len(improved[0]["signals"]) == 6


def test_learning_recommendations_empty_without_profile() -> None:
    headers = _auth_headers()
    resume_id = _create_ready_resume(headers)
    response = client.get(
        "/api/users/me/learning-recommendations",
        headers=headers,
        params={
            "resume_id": resume_id,
            "target_role": "backend",
            "interview_type": "experienced",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["has_learning_profile"] is False
    assert payload["repeat_weak_signals"] == []
