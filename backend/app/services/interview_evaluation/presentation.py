"""评估展示文案（状态标签、低分校准）。"""
from __future__ import annotations


def resolve_competency_status_label(status: str, score: int | None = None) -> str:
    if status == "verified":
        return "表现较好"
    if status == "unverified":
        return "本场讨论不足，暂无法判断"
    if status == "partially_verified":
        if isinstance(score, int) and score <= 2:
            return "明显不足，未达基本要求"
        if isinstance(score, int) and score == 3:
            return "基本到位，仍有明显缺口"
        return "有亮点，仍需加强"
    return "待观察"


def is_low_competency_score(status: str, score: int | None) -> bool:
    return status == "partially_verified" and isinstance(score, int) and score <= 2
