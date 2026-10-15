"""首问生成：以 plan opening_question 为单一来源，禁止 LLM 改写。

v3 根因改造：1.2 删除"口语化" LLM 改写分支——LLM 失败时整事务回滚，
为了避免额度浪费，回到 plan.opening_question 文本。口语化由 prompt 强约束。
"""
from __future__ import annotations

from typing import Any


def render_opening_question(
    topic: dict[str, Any],
    *,
    interview_type: str,
    trace_id: str = "",
    language: str = "en",
) -> str:
    """1.2：直接返回 plan 内的 opening_question 文本，不再调用 LLM。"""
    source = str(topic.get("opening_question", "")).strip()
    if source:
        return source
    if language == "zh":
        name = str(topic.get("name", "")).strip() or "这个方向"
        return f"请结合你的经历，谈谈在{name}方面的具体实践。"
    name = str(topic.get("name", "")).strip() or "this area"
    return f"Please share a specific experience related to {name}."
