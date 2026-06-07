"""回复处理：LangGraph 编排入口。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
