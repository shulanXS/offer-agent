"""首问生成：以 plan opening_question 为语义来源，允许口语化。"""
from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.llm.factory import create_llm_client, extract_spoken_message


logger = logging.getLogger("uvicorn.error")

_SPOKEN_JSON_SYSTEM_PROMPT = "你是结构化输出助手，只能返回 JSON，不要输出解释、示例或 Markdown。"


def render_opening_question(
    topic: dict[str, Any],
    *,
    interview_type: str,
    trace_id: str = "",
) -> str:
    source = str(topic.get("opening_question", "")).strip()
    if not source:
        name = str(topic.get("name", "")).strip() or "这个方向"
        source = f"请结合你的经历，谈谈在{name}方面的具体实践。"

    client = create_llm_client(settings.llm_provider, settings.llm_model)

    objective = str(topic.get("objective", "")).strip()
    dimension = str(topic.get("dimension", "")).strip()
    interview_label = "校招" if interview_type == "campus" else "社招"
    prompt = f"""
你是专业{interview_label}面试官。请将下列计划内开场题改写为更自然、口语化的一句提问。

要求：
1. 只返回 JSON：{{"message": "..."}}
2. 不得改变考察 intent，不得换成无关方向
3. 40-120 字，一次只问一个问题
4. 称呼候选人用「你」，不要用「您」（模拟面试口语场景）
5. 不要泄露「计划」「opening_question」等内部信息

主题：{topic.get("name", "")}
考察目标：{objective}
考察维度：{dimension}
计划内开场题：{source}
"""
    try:
        payload = client.generate_json(
            prompt,
            _SPOKEN_JSON_SYSTEM_PROMPT,
            operation_name="interview_opening_oralize",
            trace_id=trace_id,
        )
        message = extract_spoken_message(payload)
        if message:
            return message
    except Exception:
        logger.exception("[trace_id=%s] opening oralize failed, using plan text fallback", trace_id or "-")
    return source
