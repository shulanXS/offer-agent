"""切题前主题摘要（05 小步 1：证据化规则摘要 + 可选 LLM 压缩）。"""
from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.llm.factory import create_llm_client, extract_spoken_message


logger = logging.getLogger("uvicorn.error")

_SUMMARY_SYSTEM_PROMPT = "你是结构化输出助手，只能返回 JSON，不要输出解释或 Markdown。"
_SNIPPET_MAX_LEN = 120


def build_topic_summary(
    *,
    topic: dict[str, Any],
    user_answer: str = "",
    topic_messages: list[dict[str, Any]] | None = None,
    trace_id: str = "",
) -> str:
    messages = topic_messages or []
    combined_user_text = _collect_user_text(messages, fallback=user_answer)
    if _should_try_llm_summary(messages=messages, combined_user_text=combined_user_text):
        llm_summary = _build_llm_topic_summary(
            topic=topic,
            topic_messages=messages,
            combined_user_text=combined_user_text,
            trace_id=trace_id,
        )
        if llm_summary:
            return llm_summary
    return build_rule_topic_summary(
        topic=topic,
        topic_messages=messages,
        user_answer=user_answer,
    )


def build_rule_topic_summary(
    *,
    topic: dict[str, Any],
    topic_messages: list[dict[str, Any]] | None = None,
    user_answer: str = "",
) -> str:
    name = str(topic.get("name", "")).strip() or "当前主题"
    objective = str(topic.get("objective", "")).strip()
    combined_user_text = _collect_user_text(topic_messages or [], fallback=user_answer)
    snippet = _truncate_snippet(combined_user_text or user_answer)

    covered_signals = _match_plan_signals(topic, combined_user_text)
    missing_signals = _missing_plan_signals(topic, covered_signals)

    signal_part = ""
    if covered_signals:
        signal_part = f"已涉及期望信号：{'、'.join(covered_signals)}。"
    if missing_signals:
        signal_part += f"待补信号：{'、'.join(missing_signals[:3])}。"

    if objective:
        base = f"主题「{name}」（{objective}）：候选人已作答。"
    else:
        base = f"主题「{name}」：候选人已作答。"

    parts = [base]
    if signal_part:
        parts.append(signal_part)
    parts.append(f"要点：{snippet or '（无有效内容）'}")
    return " ".join(parts)


def _should_try_llm_summary(*, messages: list[dict[str, Any]], combined_user_text: str) -> bool:
    min_chars = settings.interview_topic_summary_llm_min_chars
    if min_chars <= 0:
        return False
    if len(combined_user_text) >= min_chars:
        return True
    return len(messages) >= settings.interview_context_max_messages


def _build_llm_topic_summary(
    *,
    topic: dict[str, Any],
    topic_messages: list[dict[str, Any]],
    combined_user_text: str,
    trace_id: str,
) -> str:
    client = create_llm_client(settings.llm_provider, settings.llm_model)
    history = _format_topic_messages(topic_messages)
    expected_signals = topic.get("expected_signals") or []
    focus_points = topic.get("focus_points") or []
    prompt = f"""
请将下列主题对话压缩为 1-3 句中文摘要，供后续面试轮次参考。

要求：
1. 只返回 JSON：{{"summary": "..."}}
2. 保留候选人原话要点，不得编造未出现的事实
3. 若对话涉及 plan 期望信号，在摘要中点名已讨论的信号（使用 plan 原文）
4. 80-220 字

主题：{topic.get("name", "")}
考察目标：{topic.get("objective", "")}
期望信号：{expected_signals}
关注点：{focus_points}

对话：
{history}

候选人综合表述：
{combined_user_text}
"""
    try:
        payload = client.generate_json(
            prompt,
            _SUMMARY_SYSTEM_PROMPT,
            operation_name="interview_topic_summary",
            trace_id=trace_id,
        )
        if isinstance(payload, dict):
            summary = str(payload.get("summary", "")).strip()
            if summary:
                return summary
            message = extract_spoken_message(payload)
            if message:
                return message
    except Exception:
        logger.exception("[trace_id=%s] topic summary LLM failed, using rule fallback", trace_id or "-")
    return ""


def _collect_user_text(messages: list[dict[str, Any]], *, fallback: str) -> str:
    parts = [
        str(message.get("content", "")).strip()
        for message in messages
        if message.get("role") == "user" and str(message.get("content", "")).strip()
    ]
    if parts:
        return " ".join(parts)
    return fallback.strip()


def _match_plan_signals(topic: dict[str, Any], user_text: str) -> list[str]:
    if not user_text.strip():
        return []
    normalized_text = user_text.lower()
    matched: list[str] = []
    for signal in _plan_signal_candidates(topic):
        token = signal.strip()
        if not token:
            continue
        if token.lower() in normalized_text or token in user_text:
            matched.append(signal)
    return matched


def _missing_plan_signals(topic: dict[str, Any], covered: list[str]) -> list[str]:
    covered_set = set(covered)
    return [signal for signal in _plan_signal_candidates(topic) if signal not in covered_set]


def _plan_signal_candidates(topic: dict[str, Any]) -> list[str]:
    signals: list[str] = []
    for key in ("expected_signals", "focus_points"):
        for item in topic.get(key) or []:
            text = str(item).strip()
            if text and text not in signals:
                signals.append(text)
    return signals


def _truncate_snippet(text: str) -> str:
    snippet = " ".join(text.split())
    if len(snippet) > _SNIPPET_MAX_LEN:
        return f"{snippet[:_SNIPPET_MAX_LEN]}…"
    return snippet


def _format_topic_messages(messages: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for message in messages:
        role = message.get("role")
        content = str(message.get("content", "")).strip()
        if not content:
            continue
        if role == "assistant":
            lines.append(f"面试官: {content}")
        elif role == "user":
            lines.append(f"候选人: {content}")
    return "\n".join(lines) or "（暂无对话）"
