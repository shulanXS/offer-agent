"""域 3.2 验证：日志脱敏 + 截断。"""
from __future__ import annotations

import importlib

from app.core.logging_utils import _redact_payload_recursive, _serialize_payload


def test_redact_resume_text_field() -> None:
    """resume_text 字段整体替换为 <redacted len=N>，不含原文。"""
    payload = {"resume_text": "张三 13812345678 清华大学"}
    result = _redact_payload_recursive(payload)
    assert result["resume_text"] == f"<redacted len={len('张三 13812345678 清华大学')}>"
    assert "张三" not in str(result)
    assert "13812345678" not in str(result)


def test_redact_nested_content_field() -> None:
    payload = {"user": {"content": "李四 13900001111"}}
    result = _redact_payload_recursive(payload)
    expected_len = len("李四 13900001111")
    assert result["user"]["content"] == f"<redacted len={expected_len}>"
    assert "李四" not in str(result)


def test_redact_prompt_field() -> None:
    payload = {"prompt": "Write a story about 王五"}
    result = _redact_payload_recursive(payload)
    expected_len = len("Write a story about 王五")
    assert result["prompt"] == f"<redacted len={expected_len}>"


def test_pii_in_non_deny_field_still_redacted() -> None:
    """非敏感字段的字符串走 redact_pii（手机号仍被脱敏）。"""
    payload = {"message": "用户手机号 13812345678"}
    result = _redact_payload_recursive(payload)
    assert "13812345678" not in str(result)
    assert "用户手机号" in str(result)


def test_log_truncation_1000_chars(monkeypatch) -> None:
    from app.core import config as cfg
    monkeypatch.setattr(cfg.settings, "log_payload_max_chars", 1000)
    from app.core import logging_utils as lu
    importlib.reload(lu)
    long_payload = {"text": "x" * 3000}
    result = lu._serialize_payload(long_payload)
    assert len(result) <= 1020  # 1000 chars + "\n... [truncated]" suffix
    assert "... [truncated]" in result


def test_log_truncation_short_payload_no_truncate(monkeypatch) -> None:
    from app.core import config as cfg
    monkeypatch.setattr(cfg.settings, "log_payload_max_chars", 1000)
    from app.core import logging_utils as lu
    importlib.reload(lu)
    short_payload = {"text": "hello"}
    result = lu._serialize_payload(short_payload)
    assert "... [truncated]" not in result


def test_serialize_payload_with_deny_field() -> None:
    """_serialize_payload 走递归脱敏后再序列化。"""
    payload = {"resume_text": "赵六 13700009999"}
    result = _serialize_payload(payload)
    expected_len = len("赵六 13700009999")
    assert f"<redacted len={expected_len}>" in result
    assert "13700009999" not in result
    assert "赵六" not in result
