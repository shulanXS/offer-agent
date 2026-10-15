"""首问生成：以 plan opening_question 为语义来源，允许口语化。v1.1: 中英双版。"""
from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.llm.factory import create_llm_client, extract_spoken_message


logger = logging.getLogger("uvicorn.error")

_SPOKEN_JSON_SYSTEM_PROMPT_ZH = "你是结构化输出助手，只能返回 JSON，不要输出解释、示例或 Markdown。"
_SPOKEN_JSON_SYSTEM_PROMPT_EN = "You are a structured output assistant. Return JSON only. No explanations, examples, or markdown."


def render_opening_question(
    topic: dict[str, Any],
    *,
    interview_type: str,
    trace_id: str = "",
    language: str = "en",
) -> str:
    source = str(topic.get("opening_question", "")).strip()
    if not source:
        if language == "zh":
            name = str(topic.get("name", "")).strip() or "这个方向"
            source = f"请结合你的经历，谈谈在{name}方面的具体实践。"
        else:
            name = str(topic.get("name", "")).strip() or "this area"
            source = f"Please share a specific experience related to {name}."

    client = create_llm_client(settings.llm_provider, settings.llm_model)
    is_zh = language == "zh"
    objective = str(topic.get("objective", "")).strip()
    dimension = str(topic.get("dimension", "")).strip()
    if is_zh:
        interview_label = "校招" if interview_type == "campus" else "社招"
        system_prompt = _SPOKEN_JSON_SYSTEM_PROMPT_ZH
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
    else:
        interview_label = "Campus" if interview_type == "campus" else "Experienced"
        system_prompt = _SPOKEN_JSON_SYSTEM_PROMPT_EN
        prompt = f"""
You are a professional {interview_label.lower()} interviewer. Rewrite the following planned opening question into a more natural, conversational single question.

Requirements:
1. Return JSON only: {{"message": "..."}}
2. Do not change the assessment intent or pivot to unrelated areas.
3. 40-120 words; ask one question at a time.
4. Use casual 'you' (not formal address); keep the mock-interview tone.
5. Do not reveal internal terms like "plan" or "opening_question".

Topic: {topic.get("name", "")}
Objective: {objective}
Dimension: {dimension}
Planned opening: {source}
"""
    try:
        payload = client.generate_json(
            prompt,
            system_prompt,
            operation_name="interview_opening_oralize",
            trace_id=trace_id,
        )
        message = extract_spoken_message(payload)
        if message:
            return message
    except Exception:
        logger.exception("[trace_id=%s] opening oralize failed, using plan text fallback", trace_id or "-")
    return source
