"""E2：端到端 HTTP 测试（register → upload → plan → activate → reply → evaluate）。"""
from __future__ import annotations

import os
import sys
from io import BytesIO
from pathlib import Path
from typing import Generator

import pytest

# v1.1: E2E 测试需要真 LLM（依赖 OPENAI_API_KEY），CI 默认跳过。
# 设置 RUN_E2E=1 才会跑。其它单元测试不依赖网络。
_REQUIRES_LLM = pytest.mark.skipif(
    "RUN_E2E" not in os.environ,
    reason="E2E test requires a real LLM provider; set RUN_E2E=1 to enable",
)
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path: Path) -> Generator[TestClient, None, None]:
    """干净的测试客户端，使用临时数据库，模块隔离防止污染全局状态。"""
    tmp_db = tmp_path / "test.db"

    # v1.1: Settings 的 .env 路径写死为 backend/.env，无法用 tmp_path 替换。
    # 改为：测试时把真实 backend/.env 重命名 → backend/.env.bak，写一份临时 .env。
    env_file = Path(__file__).resolve().parent.parent / ".env"
    backup_file = env_file.with_suffix(".env.bak")
    had_env = env_file.exists()
    if had_env:
        env_file.rename(backup_file)
    env_file.write_text(
        f"LLM_PROVIDER=openai\n"
        f"LLM_MODEL=gpt-4o-mini\n"
        f"OPENAI_API_KEY=test-key\n"
        f"DATABASE_PATH={tmp_db}\n"
        f"JWT_SECRET=test-jwt-secret-for-testing-only-12345\n"
        f"LOG_PAYLOAD_MAX_CHARS=2000\n"
    )

    # 清理 app.* 模块缓存
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("app."):
            del sys.modules[mod_name]

    old_cwd = os.getcwd()
    os.chdir(str(tmp_path))

    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from app.core.config import settings  # noqa: F401  (import-time instance)
        from app.db.store import init_db
        from app.main import app as fastapi_app

        init_db()
        yield TestClient(fastapi_app)
    finally:
        os.chdir(old_cwd)
        # 恢复 .env
        env_file.unlink(missing_ok=True)
        if had_env:
            backup_file.rename(env_file)


def _register_and_get_token(client: TestClient, username: str = "testuser", password: str = "testpass") -> str:
    resp = client.post("/api/auth/register", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _upload_resume(client: TestClient, token: str, content: bytes = "Name: Test\nExperience: 3 years backend\nProject: Order system".encode()) -> str:
    resp = client.post(
        "/api/resumes/extract",
        files={"file": ("resume.txt", BytesIO(content), "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_register(client: TestClient) -> None:
    resp = client.post("/api/auth/register", json={"username": "e2e_reg", "password": "pass123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["username"] == "e2e_reg"


def test_register_duplicate_username(client: TestClient) -> None:
    username = "dup_user"
    client.post("/api/auth/register", json={"username": username, "password": "pass123"})
    resp = client.post("/api/auth/register", json={"username": username, "password": "pass123"})
    assert resp.status_code == 409


def test_upload_resume_requires_auth(client: TestClient) -> None:
    resp = client.post(
        "/api/resumes/extract",
        files={"file": ("r.txt", BytesIO(b"test"), "text/plain")},
    )
    assert resp.status_code == 401


def test_create_interview_requires_auth(client: TestClient) -> None:
    resp = client.post(
        "/api/interviews",
        json={"resume_id": "fake", "interview_type": "experienced", "target_role": "backend"},
    )
    assert resp.status_code == 401


@_REQUIRES_LLM
def test_create_interview_flow(client: TestClient) -> None:
    token = _register_and_get_token(client, "e2e_flow", "pass123")
    headers = _auth_headers(token)
    resume_id = _upload_resume(client, token)

    resp = client.post(
        "/api/interviews",
        json={
            "resume_id": resume_id,
            "interview_type": "experienced",
            "target_role": "backend",
            "language": "python",
            "target_level": "intermediate",
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "session_id" in data
    assert data["status"] in ("plan_ready", "plan_confirmed")


@_REQUIRES_LLM
def test_plan_regenerate_and_confirm(client: TestClient) -> None:
    token = _register_and_get_token(client, "e2e_regen", "pass")
    headers = _auth_headers(token)
    resume_id = _upload_resume(client, token)

    # 创建
    resp = client.post(
        "/api/interviews",
        json={
            "resume_id": resume_id,
            "interview_type": "campus",
            "target_role": "frontend",
            "language": "javascript",
            "target_level": "beginner",
        },
        headers=headers,
    )
    session_id = resp.json()["session_id"]

    # 重新生成
    resp = client.post(
        f"/api/interviews/{session_id}/plan/regenerate",
        json={"additional_instruction": "重点考察框架原理"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    # 确认
    resp = client.post(f"/api/interviews/{session_id}/plan/confirm", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "plan_confirmed"


@_REQUIRES_LLM
def test_activate_and_finish(client: TestClient) -> None:
    token = _register_and_get_token(client, "e2e_live", "pass")
    headers = _auth_headers(token)
    resume_id = _upload_resume(client, token)

    # 创建并确认
    resp = client.post(
        "/api/interviews",
        json={
            "resume_id": resume_id,
            "interview_type": "experienced",
            "target_role": "fullstack",
            "language": "python",
            "target_level": "challenge",
        },
        headers=headers,
    )
    session_id = resp.json()["session_id"]
    client.post(f"/api/interviews/{session_id}/plan/confirm", headers=headers)

    # 激活
    resp = client.post(f"/api/interviews/{session_id}/activate", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "active"

    # 结束
    resp = client.post(f"/api/interviews/{session_id}/finish", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] in ("evaluating", "completed")


def test_healthz(client: TestClient) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
