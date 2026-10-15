"""v2.2 算法题：题库 + judge JSON 解析。"""
from __future__ import annotations

import importlib
import json
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def algo_module(monkeypatch, tmp_path):
    db_file = str(tmp_path / "algo.db")
    monkeypatch.setenv("DATABASE_PATH", db_file)
    from app.core import config as cfg
    importlib.reload(cfg)
    from app.db import store as store_mod
    importlib.reload(store_mod)
    store_mod.init_db()
    from app.services import algorithm_judge_service
    importlib.reload(algorithm_judge_service)
    return algorithm_judge_service


def test_list_problems_returns_at_least_one(algo_module) -> None:
    items = algo_module.list_problems()
    assert len(items) >= 1
    for item in items:
        assert "id" in item
        assert "prompt" in item
        assert "difficulty" in item


def test_get_problem_404(algo_module) -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        algo_module.get_problem("does-not-exist")
    assert exc.value.status_code == 404


def test_judge_parses_llm_json(algo_module, monkeypatch) -> None:
    captured: dict = {}

    def fake_generate_text(*, prompt, system_prompt, operation_name=""):
        captured["prompt"] = prompt
        captured["system_prompt"] = system_prompt
        return json.dumps(
            {
                "per_test": [
                    {"input": {"nums": [2, 7], "target": 9}, "expected": [0, 1], "actual": [0, 1], "pass": True, "reason": ""}
                ],
                "scores": {"correctness": 5, "efficiency": 4, "style": 4, "edge_cases": 3},
                "overall": 4.0,
                "feedback": "Looks good",
            }
        )

    monkeypatch.setattr(algo_module, "create_llm_client", lambda provider=None: MagicMock(generate_text=fake_generate_text))
    result = algo_module.judge_submission(problem_id="two_sum", code="def two_sum(a, b):\n    return [0, 1]\n", language="python")
    assert result["verdict"] == "judged"
    assert result["scores"]["correctness"] == 5.0
    assert result["scores"]["efficiency"] == 4.0
    assert result["overall"] == 4.0
    assert result["feedback"] == "Looks good"
    assert "problem" in captured["prompt"].lower()


def test_judge_handles_malformed_llm_response(algo_module, monkeypatch) -> None:
    def fake_generate_text(*, prompt, system_prompt, operation_name=""):
        return "not json at all"

    monkeypatch.setattr(algo_module, "create_llm_client", lambda provider=None: MagicMock(generate_text=fake_generate_text))
    result = algo_module.judge_submission(problem_id="two_sum", code="def x(): pass", language="python")
    assert result["verdict"] == "unparsed"
    assert result["overall"] == 0


def test_judge_rejects_empty_code(algo_module) -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        algo_module.judge_submission(problem_id="two_sum", code="", language="python")
    assert exc.value.status_code in (400, 422)
