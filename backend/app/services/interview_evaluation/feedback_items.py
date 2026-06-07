"""候选人反馈条目（title + body）。"""
from __future__ import annotations

import re
from typing import Any


def make_feedback_item(*, title: str, body: str) -> dict[str, str]:
    clean_title = str(title).strip()
    clean_body = str(body).strip()
    return {"title": clean_title, "body": clean_body}


def feedback_item_text(item: dict[str, Any] | str) -> str:
    normalized = normalize_feedback_item(item)
    if not normalized:
        return str(item).strip()
    title = normalized["title"]
    body = normalized["body"]
    if title and body:
        return f"{title}：{body}"
    return title or body


def feedback_item_key(item: dict[str, Any]) -> tuple[str, str]:
    return str(item.get("title", "")).strip(), str(item.get("body", "")).strip()


def normalize_feedback_item(value: Any) -> dict[str, str] | None:
    if isinstance(value, dict):
        title = str(value.get("title", "")).strip()
        body = str(value.get("body", "")).strip()
        if title and body:
            return make_feedback_item(title=title, body=body)
        return None

    text = str(value).strip()
    if not text:
        return None
    return feedback_item_from_legacy_text(text)


def normalize_feedback_list(value: Any, *, limit: int) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []

    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in value:
        parsed = normalize_feedback_item(item)
        if not parsed:
            continue
        key = feedback_item_key(parsed)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(parsed)
        if len(normalized) >= limit:
            break
    return normalized


def feedback_item_from_legacy_text(text: str) -> dict[str, str]:
    trimmed = text.strip()
    bracket_match = re.match(r"^「([^」]+)」(.+)?$", trimmed, flags=re.S)
    if bracket_match:
        title = bracket_match.group(1).strip()
        body = (bracket_match.group(2) or "").strip() or trimmed
        return make_feedback_item(title=title, body=body)

    colon_index = trimmed.find("：")
    if 0 < colon_index <= 24:
        return make_feedback_item(
            title=trimmed[:colon_index].strip(),
            body=trimmed[colon_index + 1 :].strip() or trimmed,
        )

    if len(trimmed) <= 18:
        return make_feedback_item(title=trimmed, body=trimmed)

    split_at = -1
    for index, char in enumerate(trimmed):
        if char in "。；;" and 0 < index <= 24:
            split_at = index
            break
    if split_at > 0:
        return make_feedback_item(
            title=trimmed[:split_at].strip(),
            body=trimmed[split_at + 1 :].strip() or trimmed,
        )

    return make_feedback_item(title=trimmed[:18].strip(), body=trimmed)
