"""回复处理：LangGraph 编排入口。

R6：彻底删 LLMStreamPatcher，改用 LangGraph 原生 `astream_events(version="v2")`：
- 节点保持同步；LangGraph 自动在内部调度，astream_events 提供
  `on_chat_model_stream` 事件，携带 LLM 真实 token delta。
- 不再 monkey-patch LLM client，也不再走 ContextVar。
- 调用方订阅 event 流，过滤 `on_chat_model_stream` 事件，提取 content 推 queue。
"""
from __future__ import annotations

import asyncio
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
        """同步路径：LangGraph invoke。"""
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
        return _outcome_from_result(result)

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
        """R6：真接 LLM 流 — 通过 LangGraph `astream_events(version="v2")` 监听
        `on_chat_model_stream` 事件，把 LLM 真实 token delta 推到 queue。
        
        节点的 invoke 仍在默认线程池跑（不会阻塞事件循环）。
        调用方负责消费 delta_queue。
        """
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

        collected_deltas: list[str] = []

        # 关键：astream_events 必须从 async 上下文调用；底层走 LangChain Runnable
        # 调度节点（同步节点会跑在线程池里）。我们订阅 on_chat_model_stream
        # 事件拿 LLM token delta。
        result: dict[str, Any] | None = None
        async for event in interview_reply_graph.astream_events(
            initial_state, version="v2",
        ):
            kind = event.get("event")
            if kind == "on_chat_model_stream" and delta_queue is not None:
                data = event.get("data") or {}
                chunk = data.get("chunk")
                if chunk is None:
                    continue
                # LangChain message chunk：content 可能是 str 或 list[dict]
                content = getattr(chunk, "content", None)
                if content is None and isinstance(chunk, dict):
                    content = chunk.get("content")
                if not content:
                    continue
                if isinstance(content, list):
                    # 拼装多模态/工具调用的文本部分
                    parts: list[str] = []
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            parts.append(str(item.get("text", "")))
                        elif isinstance(item, str):
                            parts.append(item)
                    delta = "".join(parts)
                else:
                    delta = str(content)
                if not delta:
                    continue
                collected_deltas.append(delta)
                try:
                    delta_queue.put_nowait(delta)
                except asyncio.QueueFull:
                    # 队列满：丢弃新 delta（前端已断连/限速）
                    pass
            elif kind == "on_chain_end" and event.get("name") in (None, "LangGraph", "StateGraph"):
                # 最终输出节点
                output = (event.get("data") or {}).get("output")
                if isinstance(output, dict) and "assistant_content" in output:
                    result = output

        # 兜底：若 astream_events 没透出 output（理论不会发生），回退到 invoke
        if result is None:
            result = interview_reply_graph.invoke(initial_state)

        return _outcome_from_result(result), collected_deltas


def _outcome_from_result(result: dict[str, Any]) -> ReplyOutcome:
    return ReplyOutcome(
        assistant_content=str(result["assistant_content"]),
        assistant_kind=str(result["assistant_kind"]),
        assistant_meta=dict(result["assistant_meta"]),
        runtime_state=dict(result["runtime_state"]),
        next_status=str(result["next_status"]),
        decision=dict(result["decision"]),
    )
