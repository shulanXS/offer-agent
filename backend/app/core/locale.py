"""v1.1: Accept-Language 解析。

- 仅支持 en | zh，其它 fallback en
- 取首个匹配；q 值越大越优先
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request

SUPPORTED = ("en", "zh")
DEFAULT = "en"


def parse_accept_language(value: str | None) -> str:
    if not value:
        return DEFAULT
    for raw in value.split(","):
        tag = raw.split(";", 1)[0].strip().lower()
        if not tag:
            continue
        primary = tag.split("-", 1)[0]
        if primary in SUPPORTED:
            return primary
    return DEFAULT


def resolve_locale(request: "Request") -> str:
    """v2.5: 从 request.state.locale / Accept-Language 解析 locale。"""
    state_locale = getattr(request.state, "locale", None)
    if state_locale in SUPPORTED:
        return state_locale
    return parse_accept_language(request.headers.get("accept-language"))
