"""Act 话术承接辅助（05 小步 3）。"""
from __future__ import annotations


def short_answer_snippet(latest_answer: str, *, max_len: int = 36) -> str:
    cleaned = " ".join(str(latest_answer or "").split())
    if not cleaned:
        return ""
    for separator in ("。", "；", ";", "，", ",", " "):
        if separator in cleaned:
            head = cleaned.split(separator, 1)[0].strip()
            if head:
                cleaned = head
                break
    if len(cleaned) > max_len:
        return f"{cleaned[:max_len]}…"
    return cleaned


def build_answer_bridge(latest_answer: str) -> str:
    snippet = short_answer_snippet(latest_answer)
    if not snippet:
        return "好的，"
    if snippet.endswith(("。", "！", "？")):
        return f"{snippet}"
    return f"{snippet}。"
