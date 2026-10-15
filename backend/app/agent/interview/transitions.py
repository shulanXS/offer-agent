"""切题过渡话术。v1.1: 中英双版。"""
from __future__ import annotations

from typing import Any

from app.agent.interview.opening import render_opening_question


def build_topic_handoff_message(
    *,
    completed_topic: dict[str, Any],
    next_topic: dict[str, Any],
    interview_type: str,
    trace_id: str = "",
    interview_language: str = "en",
) -> str:
    completed_name = str(completed_topic.get("name", "")).strip() or ("the previous direction" if interview_language == "en" else "刚才的方向")
    next_name = str(next_topic.get("name", "")).strip() or ("the next direction" if interview_language == "en" else "下一个方向")
    opening = render_opening_question(
        next_topic,
        interview_type=interview_type,
        trace_id=trace_id,
        language=interview_language,
    )
    if interview_language == "zh":
        transition = f"好的，{completed_name}我们先聊到这里。接下来想听听你在「{next_name}」方面的经历。"
    else:
        transition = f"Great, that covers {completed_name}. Now let's talk about {next_name}."
    return f"{transition}\n\n{opening}"


def build_completion_message(*, topic_count: int, language: str = "en") -> str:
    if language == "zh":
        return (
            f"好的，本次模拟面试的 {topic_count} 个考察方向都已覆盖。"
            "感谢你的回答，系统正在整理本场面试记录，评估报告将在后续版本提供。"
        )
    return (
        f"Great, that wraps up the {topic_count} planned topic(s) for this mock interview. "
        "Thanks for your answers. We're now summarizing this session; the evaluation report will be available shortly."
    )


def build_early_finish_message(*, reason: str = "user", language: str = "en") -> str:
    if language == "zh":
        if reason == "user":
            return "你已主动结束本次模拟面试。感谢参与，系统正在整理本场记录，评估报告将在后续版本提供。"
        if reason == "deadline_reached":
            return "本场模拟面试已到达预定时间。感谢你的回答，系统正在整理记录，评估报告将在后续版本提供。"
        if reason == "max_answer_rounds":
            return "本场模拟面试已达到回答轮数上限。感谢你的回答，系统正在整理记录，评估报告将在后续版本提供。"
        return "本场模拟面试已结束。感谢你的回答，系统正在整理记录，评估报告将在后续版本提供。"
    if reason == "user":
        return "You've ended the mock interview early. Thanks for participating; the system is now summarizing this session and the evaluation report will be available shortly."
    if reason == "deadline_reached":
        return "This mock interview has reached the planned time. Thanks for your answers; the system is now summarizing and the evaluation report will be available shortly."
    if reason == "max_answer_rounds":
        return "This mock interview has hit the answer-round limit. Thanks for your answers; the system is now summarizing and the evaluation report will be available shortly."
    return "The mock interview has ended. Thanks for your answers; the system is now summarizing and the evaluation report will be available shortly."
