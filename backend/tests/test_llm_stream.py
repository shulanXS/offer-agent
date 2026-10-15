"""A3：真接 LLM stream 测试。"""
import asyncio
from typing import Any, AsyncIterator

import pytest


def test_supports_streaming_true_for_langchain(monkeypatch) -> None:
    from app.llm.factory import LangChainLLMClient, _FakeStreamModel

    client = LangChainLLMClient("test", "test", _FakeStreamModel())
    assert client.supports_streaming() is True


def test_supports_streaming_false_for_legacy() -> None:
    from app.llm.factory import LLMClient

    class LegacyClient(LLMClient):
        provider_name = "legacy"
        model_name = "legacy"

        def generate_text(self, prompt, system_prompt=None, *, operation_name="generic", trace_id=""):
            return ""

    assert LegacyClient().supports_streaming() is False


def test_stream_text_yields_chunks() -> None:
    """stream_text 应异步逐段 yield 文本。"""
    from app.llm.factory import LangChainLLMClient, _FakeStreamModel

    client = LangChainLLMClient("test", "test", _FakeStreamModel())
    out = []

    async def _consume() -> None:
        async for chunk in client.stream_text("hello", operation_name="test"):
            out.append(chunk)

    asyncio.run(_consume())
    # 至少有 1 个非空 yield
    assert any(c for c in out)


def test_stream_text_fallback_to_generate() -> None:
    """不支持流式的 client 应回退到 generate_text 一次性 yield。"""
    from app.llm.factory import LLMClient

    class SyncOnlyClient(LLMClient):
        provider_name = "sync"
        model_name = "sync"

        def generate_text(self, prompt, system_prompt=None, *, operation_name="generic", trace_id=""):
            return "full-response"

        def supports_streaming(self):
            return False

    client = SyncOnlyClient()
    out = []

    async def _consume() -> None:
        async for chunk in client.stream_text("p", operation_name="t"):
            out.append(chunk)

    asyncio.run(_consume())
    assert "".join(out) == "full-response"


def test_enqueue_chunks_sync_basic() -> None:
    from app.services.interview.reply_handler import _enqueue_chunks_sync

    q: asyncio.Queue[str] = asyncio.Queue()
    collected: list[str] = []
    _enqueue_chunks_sync(q, "abcdefghij", collected)
    assert len(collected) >= 2
    # 拼回去应该 = 原文本
    assert "".join(collected) == "abcdefghij"


def test_enqueue_chunks_sync_empty() -> None:
    from app.services.interview.reply_handler import _enqueue_chunks_sync

    q: asyncio.Queue[str] = asyncio.Queue()
    collected: list[str] = []
    _enqueue_chunks_sync(q, "", collected)
    assert collected == []


# -------------------------------------------------------------------
# 测试辅助
# -------------------------------------------------------------------


class _FakeStreamModel:
    """具备 astream 协议但实现为同步 yield 的假 model。

    不真发请求，仅做协议形状验证。
    """

    def astream(self, messages):
        async def _gen():
            for word in ["hello", " ", "world"]:
                yield _FakeChunk(word)

        return _gen()

    def invoke(self, messages):
        return _FakeChunk("hello world")


class _FakeChunk:
    def __init__(self, text: str) -> None:
        self.content = text
