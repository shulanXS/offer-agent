"""05 小步 1：主题摘要升级、工作记忆初始化与 Observe 上下文压缩。"""
from __future__ import annotations

from app.services.interview.context import build_observe_context, get_interview_memory_context
from app.services.interview.context_limits import trim_topic_messages
from app.services.interview.memory.schema import empty_working_memory, ensure_working_memory
from app.services.interview.runtime_state import build_initial_runtime_state
from app.services.interview.topic_summary import build_rule_topic_summary, build_topic_summary


def _sample_topic() -> dict:
    return {
        "id": "topic-1",
        "name": "项目深挖",
        "objective": "验证项目经历真实性",
        "expected_signals": ["个人贡献", "结果指标"],
        "focus_points": ["技术难点"],
    }


def test_initial_runtime_state_has_working_memory() -> None:
    plan_json = {"topics": [{"id": "topic-1", "name": "项目深挖", "required": True}]}
    runtime_state = build_initial_runtime_state(
        trace_id="trace-test",
        confirmed_plan_id="plan-1",
        plan_json=plan_json,
        interview_type="experienced",
    )
    working_memory = runtime_state["working_memory"]
    assert working_memory["schema_version"] == 1
    assert working_memory["claims"] == []
    assert working_memory["evidence"] == []


def test_get_interview_memory_context_reads_working_memory_shape() -> None:
    runtime_state = {
        "topic_summaries": {"topic-0": "已完成主题摘要"},
        "working_memory": empty_working_memory(),
    }
    memory = get_interview_memory_context(
        session_id="session-1",
        topic_id="topic-1",
        runtime_state=runtime_state,
    )
    assert memory["relevant_memory"]["current_topic_id"] == "topic-1"
    assert memory["relevant_memory"]["completed_topic_summary_ids"] == ["topic-0"]
    assert memory["missing_information"] == []
    assert memory["interview_knowledge"] == []


def test_trim_topic_messages_respects_limits() -> None:
    messages = [
        {"role": "user", "content": "x" * 500},
        {"role": "assistant", "content": "追问 1"},
        {"role": "user", "content": "y" * 500},
        {"role": "assistant", "content": "追问 2"},
        {"role": "user", "content": "最新回答"},
    ]
    trimmed = trim_topic_messages(messages, max_messages=3, max_chars=800)
    assert len(trimmed) <= 3
    assert sum(len(str(item.get("content", ""))) for item in trimmed) <= 800
    assert trimmed[-1]["content"] == "最新回答"


def test_build_observe_context_has_bounded_char_estimate() -> None:
    topic = _sample_topic()
    long_messages = [
        {"role": "assistant", "content": "请介绍项目。"},
        {"role": "user", "content": "回答 " + ("细节 " * 200)},
    ]
    runtime_state = {
        "current_topic_id": topic["id"],
        "topic_summaries": {"topic-0": "历史主题摘要 " * 20},
        "working_memory": empty_working_memory(),
    }
    observe_context = build_observe_context(
        plan_json={"topics": [topic]},
        configuration={"interview_type": "experienced"},
        resume=None,
        runtime_state=runtime_state,
        topic_messages=long_messages,
        latest_answer=long_messages[-1]["content"],
    )
    assert len(observe_context["context_topic_messages"]) <= len(long_messages)
    assert observe_context["context_char_estimate"] <= 4000 + 200


def test_rule_topic_summary_mentions_plan_signals() -> None:
    topic = _sample_topic()
    summary = build_rule_topic_summary(
        topic=topic,
        topic_messages=[
            {"role": "user", "content": "我独立负责消息模块，个人贡献比较明确。"},
        ],
    )
    assert "个人贡献" in summary
    assert "结果指标" in summary or "待补信号" in summary


def test_topic_summary_llm_failure_falls_back_to_rule(monkeypatch) -> None:
    from tests.support.llm_fake import patch_failing_llm_client

    patch_failing_llm_client(monkeypatch)
    topic = _sample_topic()
    summary = build_topic_summary(
        topic=topic,
        user_answer="个人贡献明确，结果指标也做了监控。",
        topic_messages=[{"role": "user", "content": "个人贡献明确，结果指标也做了监控。"}],
        trace_id="trace-fallback",
    )
    assert "项目深挖" in summary
    assert "个人贡献" in summary


def test_multi_topic_summaries_persist_after_advance() -> None:
    from fastapi.testclient import TestClient
    import uuid

    from app.db.store import Store
    from app.main import app

    client = TestClient(app)

    def _auth_headers() -> dict[str, str]:
        username = f"mem_{uuid.uuid4().hex[:8]}"
        password = "password123"
        register_response = client.post("/api/auth/register", json={"username": username, "password": password})
        token = register_response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def _create_confirmed_session(headers: dict[str, str]) -> tuple[str, dict]:
        user_id = client.get("/api/auth/me", headers=headers).json()["id"]
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
        created = client.post(
            "/api/interviews",
            headers=headers,
            json={
                "resume_id": resume["id"],
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
        plan_json = store.get_plan_by_id(created["plan_id"])["plan_json"]
        return session_id, plan_json

    headers = _auth_headers()
    session_id, plan_json = _create_confirmed_session(headers)
    user_id = client.get("/api/auth/me", headers=headers).json()["id"]
    store = Store()
    first_topic = plan_json["topics"][0]
    second_topic = plan_json["topics"][1]

    client.post(f"/api/interviews/{session_id}/activate", headers=headers)
    client.post(
        f"/api/interviews/{session_id}/reply/stream",
        headers=headers,
        json={
            "content": (
                f"关于{first_topic['name']}，我负责核心模块设计、开发、上线与结果验证，"
                "个人贡献明确，通过指标监控和灰度发布确保稳定性。"
            )
        },
    )

    record = store.get_interview_session_record(user_id, session_id)
    runtime_state = record["workflow_state"]
    assert first_topic["id"] in runtime_state["topic_summaries"]
    assert runtime_state["working_memory"]["schema_version"] == 1

    detail = client.get(f"/api/interviews/{session_id}", headers=headers).json()
    assert detail["progress"]["current_topic_id"] == second_topic["id"]

    record = store.get_interview_session_record(user_id, session_id)
    restored = record["workflow_state"]
    assert first_topic["id"] in restored["topic_summaries"]
    assert restored["topic_summaries"][first_topic["id"]]
