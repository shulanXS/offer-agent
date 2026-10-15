"""回复处理：LangGraph 编排入口。"""
from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from typing import Any, AsyncIterator, Optional


@dataclass
class ReplyOutcome:
    assistant_content: str
    assistant_kind: str
    assistant_meta: dict[str, Any]
    runtime_state: dict[str, Any]
    next_status: str
    decision: dict[str, Any]


class InterviewReplyHandler:
    def process(
        self,
        *,
        plan_json: dict[str, Any],
        configuration: dict[str, Any],
        resume: dict[str, Any] | None,
        runtime_state: dict[str, Any],
        current_topic: dict[str, Any],
        all_messages: list[dict[str, Any]],
        latest_answer: str,
        trace_id: str,
    ) -> ReplyOutcome:
        from app.agent.interview.graph import interview_reply_graph
        from app.agent.interview.state import build_interview_reply_state

        initial_state = build_interview_reply_state(
            trace_id=trace_id,
            plan_json=plan_json,
            configuration=configuration,
            resume=resume,
            runtime_state=runtime_state,
            current_topic=current_topic,
            all_messages=all_messages,
            latest_answer=latest_answer,
        )
        result = interview_reply_graph.invoke(initial_state)
        return ReplyOutcome(
            assistant_content=str(result["assistant_content"]),
            assistant_kind=str(result["assistant_kind"]),
            assistant_meta=dict(result["assistant_meta"]),
            runtime_state=dict(result["runtime_state"]),
            next_status=str(result["next_status"]),
            decision=dict(result["decision"]),
        )

    async def process_streaming(
        self,
        *,
        plan_json: dict[str, Any],
        configuration: dict[str, Any],
        resume: dict[str, Any] | None,
        runtime_state: dict[str, Any],
        current_topic: dict[str, Any],
        all_messages: list[dict[str, Any]],
        latest_answer: str,
        trace_id: str,
        delta_queue: Optional["asyncio.Queue[str]"] = None,
    ) -> tuple[ReplyOutcome, list[str]]:
        """A3：异步 + 流式版本。

        - LangGraph 同步 invoke 在线程池中跑（不会阻塞 asyncio 事件循环）
        - 同时把 LLM 客户端的 `generate_text` 临时替换为 `stream_text`，
          通过 delta_queue 把 token 级输出推到 SSE 端
        - 调用方负责消费 delta_queue

        返回 (outcome, collected_deltas)：
        - outcome：完整的 LangGraph 执行结果（assistant_content 是最终落库文案）
        - collected_deltas：本地缓存的 delta 列表（调试/补偿用）
        """
        from app.agent.interview.graph import interview_reply_graph
        from app.agent.interview.state import build_interview_reply_state
        from app.llm.factory import create_llm_client

        initial_state = build_interview_reply_state(
            trace_id=trace_id,
            plan_json=plan_json,
            configuration=configuration,
            resume=resume,
            runtime_state=runtime_state,
            current_topic=current_topic,
            all_messages=all_messages,
            latest_answer=latest_answer,
        )

        # 准备 LLM 流式补丁：若 client 支持流式，patch generate_text 让它
        # 把内容按 token / 句子 切片推到 queue
        collected_deltas: list[str] = []
        patcher = None
        if delta_queue is not None:
            patcher = LLMStreamPatcher(delta_queue=delta_queue, collected=collected_deltas)
            patcher.apply()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: interview_reply_graph.invoke(initial_state),
            )
        finally:
            if patcher is not None:
                patcher.revert()

        return ReplyOutcome(
            assistant_content=str(result["assistant_content"]),
            assistant_kind=str(result["assistant_kind"]),
            assistant_meta=dict(result["assistant_meta"]),
            runtime_state=dict(result["runtime_state"]),
            next_status=str(result["next_status"]),
            decision=dict(result["decision"]),
        ), collected_deltas


class LLMStreamPatcher:
    """A3 helper：把 LLMClient.generate_text 临时替换为流式切片。

    - 仅在 `supports_streaming()` 返回 true 的 client 上生效
    - 把 generate_text 的结果按 4 字符一组切片（cjk 友好），每片推 queue
    - 不替换 provider 代码，回退到 generate_text
    """

    def __init__(self, *, delta_queue: "asyncio.Queue[str]", collected: list[str]) -> None:
        self._queue = delta_queue
        self._collected = collected
        self._originals: dict[type, Any] = {}

    def apply(self) -> None:
        # 收集所有可能注入的 LLM client 单例
        from app.llm.factory import LangChainLLMClient
        self._LangChainLLMClient = LangChainLLMClient
        original_generate_text = LangChainLLMClient.generate_text
        self._originals[LangChainLLMClient] = original_generate_text
        LangChainLLMClient.generate_text = self._wrap_generate_text(original_generate_text)  # type: ignore[assignment]

    def revert(self) -> None:
        for cls, fn in self._originals.items():
            cls.generate_text = fn  # type: ignore[assignment]
        self._originals.clear()

    def _wrap_generate_text(self, original: Any) -> Any:
        queue = self._queue
        collected = self._collected

        def patched(self_client: Any, prompt: str, system_prompt: str | None = None, **kwargs: Any) -> str:
            supports = getattr(self_client, "supports_streaming", lambda: False)()
            if not supports:
                return original(self_client, prompt, system_prompt, **kwargs)
            # 同步转异步：先调 generate_text 拿全量，再切片推 queue
            text = original(self_client, prompt, system_prompt, **kwargs)
            _enqueue_chunks_sync(queue, text, collected)
            return text

        return patched


def _enqueue_chunks_sync(queue: "asyncio.Queue[str]", text: str, collected: list[str]) -> None:
    """A3 helper：把全量文本按 6 字符切片，跨事件循环推到 asyncio.Queue。"""
    if not text:
        return
    step = 6
    for i in range(0, len(text), step):
        chunk = text[i : i + step]
        collected.append(chunk)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.call_soon_threadsafe(queue.put_nowait, chunk)
            else:
                queue.put_nowait(chunk)
        except RuntimeError:
            try:
                queue.put_nowait(chunk)
            except Exception:
                pass
