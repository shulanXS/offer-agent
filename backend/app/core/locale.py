"""v1.1: Accept-Language 解析。

- 仅支持 en | zh，其它 fallback en
- 取首个匹配；q 值越大越优先
"""
from __future__ import annotations

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
