"""切题过渡话术（04 小步 1：模板 + 下一主题 opening）。"""
from __future__ import annotations

from typing import Any

from app.agent.interview.opening import render_opening_question


def build_topic_handoff_message(
    *,
    completed_topic: dict[str, Any],
    next_topic: dict[str, Any],
    interview_type: str,
    trace_id: str = "",
) -> str:
    completed_name = str(completed_topic.get("name", "")).strip() or "刚才的方向"
    next_name = str(next_topic.get("name", "")).strip() or "下一个方向"
    opening = render_opening_question(next_topic, interview_type=interview_type, trace_id=trace_id)
    transition = f"好的，{completed_name}我们先聊到这里。接下来想听听你在「{next_name}」方面的经历。"
    return f"{transition}\n\n{opening}"


def build_completion_message(*, topic_count: int) -> str:
    return (
        f"好的，本次模拟面试的 {topic_count} 个考察方向都已覆盖。"
        "感谢你的回答，系统正在整理本场面试记录，评估报告将在后续版本提供。"
    )


def build_early_finish_message(*, reason: str = "user") -> str:
    if reason == "user":
        return "你已主动结束本次模拟面试。感谢参与，系统正在整理本场记录，评估报告将在后续版本提供。"
    if reason == "deadline_reached":
        return "本场模拟面试已到达预定时间。感谢你的回答，系统正在整理记录，评估报告将在后续版本提供。"
    if reason == "max_answer_rounds":
        return "本场模拟面试已达到回答轮数上限。感谢你的回答，系统正在整理记录，评估报告将在后续版本提供。"
    return "本场模拟面试已结束。感谢你的回答，系统正在整理记录，评估报告将在后续版本提供。"
