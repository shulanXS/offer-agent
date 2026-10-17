"""v2.2 算法判题服务：调用 LLM 模拟运行隐藏测试 + 评分。"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.core.errors import ErrorCode, raise_app_error
from app.data.algorithm_problems import get_problem_by_id, list_problem_summaries
from app.llm.factory import create_llm_client

logger = logging.getLogger("uvicorn.error")

_JUDGE_SYSTEM_PROMPT = (
    "You are a strict but fair algorithm interview judge. "
    "Given a problem description, a candidate's solution in Python, and a list of hidden test cases "
    "with expected outputs, you must:\n"
    "  1. Mentally execute the candidate's code against each test case (do NOT actually run code).\n"
    "  2. For each test, return {'input': ..., 'expected': ..., 'actual': ..., 'pass': bool, 'reason': '...'}.\n"
    "  3. Score the solution 0-5:\n"
    "     - correctness: does it pass most hidden tests?\n"
    "     - efficiency: is the time/space complexity reasonable for the problem?\n"
    "     - style: readability, naming, comments\n"
    "     - edge_cases: null/empty/large inputs handled\n"
    "  4. Return JSON ONLY with shape:\n"
    "{\n"
    "  \"per_test\": [...],\n"
    "  \"scores\": {\"correctness\": 0-5, \"efficiency\": 0-5, \"style\": 0-5, \"edge_cases\": 0-5},\n"
    "  \"overall\": 0-5,\n"
    "  \"feedback\": \"1-2 sentence summary\"\n"
    "}\n"
    "Be honest: do not give 5/5 unless code is correct on ALL hidden tests and well styled."
)


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """从 LLM 响应里抠 JSON。容错：可能被 ```json ... ``` 包起来。"""
    text = (text or "").strip()
    # 去掉 markdown 围栏
    fence = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if fence:
        text = fence.group(1)
    # 找第一个 { 开始的平衡括号
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                snippet = text[start : i + 1]
                try:
                    return json.loads(snippet)
                except json.JSONDecodeError:
                    return None
    return None


# v2.3: 判题白名单语言 + 错误码分离
ALLOWED_JUDGE_LANGUAGES = {"python", "javascript", "typescript", "go", "java", "cpp", "c", "rust", "ruby"}


def list_problems() -> list[dict[str, Any]]:
    return list_problem_summaries()


def get_problem(pid: str) -> dict[str, Any]:
    p = get_problem_by_id(pid)
    if not p:
        # v2.3: 改用专门的算法题错误码
        raise_app_error(404, ErrorCode.ALGORITHM_PROBLEM_NOT_FOUND, "未找到该算法题")
    # 隐藏测试不返回
    return {
        "id": p["id"],
        "difficulty": p["difficulty"],
        "tags": p["tags"],
        "prompt": p["prompt"],
        "function_signature": p["function_signature"],
    }


def judge_submission(
    *,
    problem_id: str,
    code: str,
    language: str = "python",
) -> dict[str, Any]:
    problem = get_problem_by_id(problem_id)
    if not problem:
        raise_app_error(404, ErrorCode.ALGORITHM_PROBLEM_NOT_FOUND, "未找到该算法题")
    if not (code or "").strip():
        raise_app_error(400, ErrorCode.JUDGE_CODE_INVALID, "代码不能为空")

    # v2.3: language 白名单校验
    normalized_language = (language or "python").strip().lower()
    if normalized_language not in ALLOWED_JUDGE_LANGUAGES:
        raise_app_error(
            400,
            ErrorCode.JUDGE_LANGUAGE_UNSUPPORTED,
            f"暂不支持的判题语言: {language}",
            details={"allowed": sorted(ALLOWED_JUDGE_LANGUAGES)},
        )

    user_prompt = (
        f"Problem:\n{problem['prompt']}\n\n"
        f"Function signature:\n{problem['function_signature']}\n\n"
        f"Hidden tests (input/expected):\n"
        f"{json.dumps(problem['hidden_tests'], ensure_ascii=False, indent=2)}\n\n"
        f"Candidate's code ({normalized_language}):\n```\n{code}\n```\n\n"
        f"Return JSON only."
    )

    client = create_llm_client(provider=None)
    try:
        text = client.generate_text(
            prompt=user_prompt,
            system_prompt=_JUDGE_SYSTEM_PROMPT,
            operation_name="algorithm_judge",
        )
    except Exception as exc:  # v2.3: 错误码分离
        logger.exception("algorithm_judge LLM call failed: problem_id=%s", problem_id)
        raise_app_error(
            500,
            ErrorCode.JUDGE_EXECUTION_FAILED,
            "判题服务执行失败，请稍后重试",
            details={"reason": str(exc)},
        )

    parsed = _extract_json_object(text or "")
    if not parsed:
        logger.warning("algorithm_judge: failed to parse LLM response")
        return {
            "verdict": "unparsed",
            "scores": {"correctness": 0, "efficiency": 0, "style": 0, "edge_cases": 0},
            "overall": 0,
            "feedback": "判题服务暂时无法解析答案，请稍后重试。",
            "per_test": [],
        }

    # 归一化分数：1-5 范围
    scores = parsed.get("scores") or {}
    normalized = {
        "correctness": float(scores.get("correctness", 0)),
        "efficiency": float(scores.get("efficiency", 0)),
        "style": float(scores.get("style", 0)),
        "edge_cases": float(scores.get("edge_cases", 0)),
    }
    overall = float(parsed.get("overall", 0))
    # 钳制 1-5
    for k in normalized:
        normalized[k] = max(1.0, min(5.0, normalized[k]))
    overall = max(1.0, min(5.0, overall))

    return {
        "verdict": "judged",
        "scores": normalized,
        "overall": overall,
        "feedback": str(parsed.get("feedback", "")).strip(),
        "per_test": parsed.get("per_test") or [],
        "raw_response": (text or "")[:4000],
    }
