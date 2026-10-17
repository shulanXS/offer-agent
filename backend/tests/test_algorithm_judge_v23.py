"""v2.3 算法题错误码 + language 白名单测试。"""
from __future__ import annotations

import importlib
import time

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core import config as cfg
from app.core.errors import ErrorCode
from app.db import store as store_mod
from app.main import app
from app.services import algorithm_judge_service


@pytest.fixture
def fresh_db(monkeypatch, tmp_path):
    db_file = str(tmp_path / "algo.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    importlib.reload(cfg)
    importlib.reload(store_mod)
    store_mod.init_db()
    yield db_file


def test_get_problem_unknown_uses_algo_error_code() -> None:
    with pytest.raises(HTTPException) as exc:
        algorithm_judge_service.get_problem("nonexistent-problem")
    assert exc.value.status_code == 404
    assert exc.value.detail["code"] == ErrorCode.ALGORITHM_PROBLEM_NOT_FOUND


def test_judge_empty_code_uses_judge_code_invalid() -> None:
    pid = algorithm_judge_service.list_problems()[0]["id"]
    with pytest.raises(HTTPException) as exc:
        algorithm_judge_service.judge_submission(problem_id=pid, code="   ", language="python")
    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == ErrorCode.JUDGE_CODE_INVALID


def test_judge_unsupported_language_uses_judge_language_unsupported() -> None:
    pid = algorithm_judge_service.list_problems()[0]["id"]
    with pytest.raises(HTTPException) as exc:
        algorithm_judge_service.judge_submission(
            problem_id=pid, code="print(1)", language="brainfuck",
        )
    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == ErrorCode.JUDGE_LANGUAGE_UNSUPPORTED


def test_judge_endpoint_requires_auth(fresh_db) -> None:
    with TestClient(app) as client:
        r = client.post(
            "/api/algorithm/judge",
            json={"problem_id": "x", "code": "y", "language": "python"},
        )
        assert r.status_code in (401, 403)
