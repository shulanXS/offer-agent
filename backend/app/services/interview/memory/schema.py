"""工作记忆 Schema 与初始化（05 小步 1）。"""
from __future__ import annotations

from typing import Any

WORKING_MEMORY_SCHEMA_VERSION = 1

_LIST_FIELDS = (
    "claims",
    "evidence",
    "risks",
    "contradictions",
    "missing_information",
    "covered_topics",
    "uncovered_topics",
)


def empty_working_memory() -> dict[str, Any]:
    return {
        "schema_version": WORKING_MEMORY_SCHEMA_VERSION,
        "claims": [],
        "evidence": [],
        "risks": [],
        "contradictions": [],
        "missing_information": [],
        "covered_topics": [],
        "uncovered_topics": [],
    }


def ensure_working_memory(runtime_state: dict[str, Any]) -> dict[str, Any]:
    working_memory = runtime_state.get("working_memory")
    if not isinstance(working_memory, dict):
        return empty_working_memory()
    if int(working_memory.get("schema_version") or 0) != WORKING_MEMORY_SCHEMA_VERSION:
        return empty_working_memory()
    normalized = empty_working_memory()
    for key in _LIST_FIELDS:
        value = working_memory.get(key)
        if isinstance(value, list):
            normalized[key] = value
    return normalized


def attach_working_memory_if_missing(runtime_state: dict[str, Any]) -> dict[str, Any]:
    updated = dict(runtime_state)
    if "working_memory" not in updated or not isinstance(updated.get("working_memory"), dict):
        updated["working_memory"] = empty_working_memory()
    else:
        updated["working_memory"] = ensure_working_memory(updated)
    return updated
