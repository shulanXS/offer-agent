"""域 2.3 验证：extract_spoken 简化版不再做启发式。"""
from __future__ import annotations

import pytest

from app.llm.factory import (
    extract_spoken_message,
    extract_spoken_response,
    create_llm_client,
)


def test_extract_spoken_passthrough_clean_text() -> None:
    """纯英文 prompt 输出干净时，原样返回。"""
    raw = "This is a clean spoken response with no fences."
    assert extract_spoken_response(raw) == raw


def test_extract_spoken_strip_json_fence() -> None:
    raw = '```json\n{"message": "hello"}\n```'
    assert extract_spoken_response(raw) == '{"message": "hello"}'


def test_extract_spoken_strip_plain_fence() -> None:
    raw = "```\nsome text\n```"
    assert extract_spoken_response(raw) == "some text"


def test_extract_spoken_message_从_payload() -> None:
    payload = {"message": "hi there"}
    assert extract_spoken_message(payload) == "hi there"


def test_extract_spoken_message_follow_up_字段() -> None:
    payload = {"follow_up": "follow up text"}
    assert extract_spoken_message(payload) == "follow up text"


def test_create_llm_client_unknown_provider_抛错() -> None:
    """v1.0 兼容别名（claude/claude_code/volc/ark/huoshan）已收敛。"""
    with pytest.raises(ValueError, match="不支持的 LLM_PROVIDER"):
        create_llm_client(provider="claude")
    with pytest.raises(ValueError, match="不支持的 LLM_PROVIDER"):
        create_llm_client(provider="volc")
