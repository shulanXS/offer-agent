"""Planning 输出校验：规范化 LLM/模板返回的 plan JSON，校验结构与校招/社招维度覆盖。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.interview_planning.constants import PLAN_BOUNDARIES


class PlanValidationError(ValueError):
    pass


TOPIC_REQUIRED_FIELDS = (
    "id",
    "name",
    "dimension",
    "objective",
    "focus_points",
    "required",
    "estimated_minutes",
    "max_rounds",
    "opening_question",
    "expected_signals",
    "probe_strategies",
    "evaluation_criteria",
    "source_refs",
)

MAX_TOPIC_ESTIMATED_MINUTES = 15
_MIN_TOPIC_COUNT = 4
_MAX_TOPIC_COUNT = 5
_MAX_PLANNED_TOPIC_MINUTES = (
    PLAN_BOUNDARIES["duration_minutes"] - PLAN_BOUNDARIES["closing_buffer_minutes"]
)


@dataclass
class PlanValidationResult:
    plan: dict[str, Any]
    candidate_summary: dict[str, Any]


def validate_and_normalize_plan(raw: dict[str, Any], *, configuration: dict[str, Any]) -> PlanValidationResult:
    if not isinstance(raw, dict):
        raise PlanValidationError("计划输出必须是 JSON 对象")

    topics = raw.get("topics")
    if not isinstance(topics, list):
        raise PlanValidationError("topics 必须是数组")

    topics = _trim_topics_to_max_count(topics, max_count=_MAX_TOPIC_COUNT)
    topic_count = len(topics)
    if topic_count < _MIN_TOPIC_COUNT:
        raise PlanValidationError(f"主题数量必须为 {_MIN_TOPIC_COUNT} 至 {_MAX_TOPIC_COUNT} 个，当前为 {topic_count}")

    normalized_topics: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    required_count = 0
    opening_questions: list[str] = []

    for index, item in enumerate(topics, start=1):
        topic = _normalize_topic(item, index=index)
        if topic["id"] in seen_ids:
            raise PlanValidationError(f"主题 id 重复: {topic['id']}")
        seen_ids.add(topic["id"])
        if topic["required"]:
            required_count += 1
        opening_questions.append(topic["opening_question"])
        normalized_topics.append(topic)

    if required_count < 4:
        raise PlanValidationError("至少需要 4 个必考主题")

    _normalize_estimated_minutes_budget(normalized_topics)

    assert_required_dimensions(normalized_topics, interview_type=configuration["interview_type"])

    candidate_summary = _normalize_candidate_summary(raw.get("candidate_summary"), configuration=configuration)
    _assert_summary_safe(candidate_summary, opening_questions)

    plan = {
        **PLAN_BOUNDARIES,
        "topics": normalized_topics,
    }
    return PlanValidationResult(plan=plan, candidate_summary=candidate_summary)


def _trim_topics_to_max_count(topics: list[Any], *, max_count: int) -> list[Any]:
    """LLM 偶发 6+ 主题；优先丢弃非必考，避免整轮重试。"""
    items = list(topics)
    while len(items) > max_count:
        drop_index = _pick_topic_index_to_drop(items)
        items.pop(drop_index)
    return items


def _pick_topic_index_to_drop(topics: list[Any]) -> int:
    optional_indices = [
        index
        for index, item in enumerate(topics)
        if isinstance(item, dict) and not bool(item.get("required"))
    ]
    if optional_indices:
        return min(
            optional_indices,
            key=lambda index: int((topics[index] or {}).get("estimated_minutes") or 0),
        )
    return min(
        range(len(topics)),
        key=lambda index: int((topics[index] if isinstance(topics[index], dict) else {}).get("estimated_minutes") or 999),
    )


def _normalize_estimated_minutes_budget(topics: list[dict[str, Any]]) -> None:
    """LLM 常算错 minutes 总和；按比例压到预算内，避免整轮重试。"""
    budget = _MAX_PLANNED_TOPIC_MINUTES
    total = sum(int(topic["estimated_minutes"]) for topic in topics)
    if total <= budget:
        return

    weights = [int(topic["estimated_minutes"]) for topic in topics]
    scaled = [max(1, int(weight * budget / total)) for weight in weights]
    current = sum(scaled)

    while current > budget:
        index = max(range(len(scaled)), key=lambda idx: scaled[idx])
        if scaled[index] <= 1:
            break
        scaled[index] -= 1
        current -= 1

    while current < budget:
        index = max(range(len(scaled)), key=lambda idx: (weights[idx], scaled[idx]))
        if scaled[index] >= MAX_TOPIC_ESTIMATED_MINUTES:
            break
        scaled[index] += 1
        current += 1

    for topic, minutes in zip(topics, scaled, strict=True):
        topic["estimated_minutes"] = minutes


def _normalize_topic(item: Any, *, index: int) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise PlanValidationError(f"第 {index} 个主题必须是对象")

    missing = [field for field in TOPIC_REQUIRED_FIELDS if field not in item]
    if missing:
        raise PlanValidationError(f"第 {index} 个主题缺少字段: {', '.join(missing)}")

    topic_id = str(item["id"]).strip() or f"topic-{index}"
    name = str(item["name"]).strip()
    dimension = str(item["dimension"]).strip()
    objective = str(item["objective"]).strip()
    if not name or not dimension or not objective:
        raise PlanValidationError(f"第 {index} 个主题的 name/dimension/objective 不能为空")

    focus_points = _to_string_list(item["focus_points"], field=f"topics[{index}].focus_points", min_items=1, max_items=6)
    expected_signals = _to_string_list(
        item["expected_signals"], field=f"topics[{index}].expected_signals", min_items=1, max_items=6
    )
    probe_strategies = _to_string_list(
        item["probe_strategies"], field=f"topics[{index}].probe_strategies", min_items=1, max_items=4
    )
    source_refs = _to_string_list(item["source_refs"], field=f"topics[{index}].source_refs", min_items=1, max_items=6)

    opening_question = str(item["opening_question"]).strip()
    evaluation_criteria = str(item["evaluation_criteria"]).strip()
    if len(opening_question) < 8:
        raise PlanValidationError(f"第 {index} 个主题的 opening_question 过短")
    if not evaluation_criteria:
        raise PlanValidationError(f"第 {index} 个主题的 evaluation_criteria 不能为空")

    required = bool(item["required"])
    estimated_minutes = int(item["estimated_minutes"])
    max_rounds = int(item["max_rounds"])
    if estimated_minutes <= 0 or estimated_minutes > MAX_TOPIC_ESTIMATED_MINUTES:
        raise PlanValidationError(f"第 {index} 个主题的 estimated_minutes 必须在 1 至 {MAX_TOPIC_ESTIMATED_MINUTES} 之间")
    if max_rounds <= 0 or max_rounds > 3:
        raise PlanValidationError(f"第 {index} 个主题的 max_rounds 必须在 1 至 3 之间")

    return {
        "id": topic_id,
        "name": name,
        "dimension": dimension,
        "objective": objective,
        "focus_points": focus_points,
        "required": required,
        "estimated_minutes": estimated_minutes,
        "max_rounds": max_rounds,
        "opening_question": opening_question,
        "expected_signals": expected_signals,
        "probe_strategies": probe_strategies,
        "evaluation_criteria": evaluation_criteria,
        "source_refs": source_refs,
    }


def _normalize_candidate_summary(raw: Any, *, configuration: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise PlanValidationError("candidate_summary 必须是对象")

    focus_topics = _to_string_list(
        raw.get("focus_topics", configuration.get("focus_topics", [])),
        field="candidate_summary.focus_topics",
        min_items=1,
        max_items=6,
    )
    reference_summary = _to_string_list(
        raw.get("reference_summary", []),
        field="candidate_summary.reference_summary",
        min_items=1,
        max_items=4,
    )
    for item in reference_summary:
        if len(item) > 120:
            raise PlanValidationError("reference_summary 单条不能超过 120 字")

    return {
        "focus_topics": focus_topics,
        "reference_summary": reference_summary,
    }


def _assert_summary_safe(candidate_summary: dict[str, Any], opening_questions: list[str]) -> None:
    joined_summary = " ".join(candidate_summary.get("reference_summary", []))
    for question in opening_questions:
        compact_question = question.strip()
        if len(compact_question) >= 20 and compact_question in joined_summary:
            raise PlanValidationError("candidate_summary 不得泄露完整 opening_question")


def _to_string_list(raw: Any, *, field: str, min_items: int, max_items: int) -> list[str]:
    if not isinstance(raw, list):
        raise PlanValidationError(f"{field} 必须是字符串数组")
    result: list[str] = []
    for item in raw:
        text = str(item).strip()
        if text and text not in result:
            result.append(text)
    if len(result) < min_items:
        raise PlanValidationError(f"{field} 至少需要 {min_items} 项")
    if len(result) > max_items:
        raise PlanValidationError(f"{field} 最多 {max_items} 项")
    return result


CAMPUS_DIMENSION_BUCKETS: tuple[dict[str, Any], ...] = (
    {"id": "fundamentals", "label": "技术或专业基础", "aliases": ("技术", "专业基础", "基础", "原理", "fundamentals", "foundations", "principles")},
    {"id": "project", "label": "项目、实习或竞赛经历", "aliases": ("项目", "实习", "竞赛", "经历", "project", "internship", "competition", "experience")},
    {"id": "analysis", "label": "问题分析能力", "aliases": ("问题分析", "分析能力", "拆解", "problem analysis", "problem solving", "problem-solving", "analytical", "decomposition")},
    {"id": "learning", "label": "学习能力或成长潜力", "aliases": ("学习", "成长", "潜力", "learning", "growth", "potential")},
)

EXPERIENCED_DIMENSION_BUCKETS: tuple[dict[str, Any], ...] = (
    {"id": "ownership", "label": "项目所有权和个人贡献", "aliases": ("项目", "所有权", "贡献", "经历真实性", "职责", "project", "ownership", "contribution", "responsibility")},
    {"id": "depth", "label": "技术深度", "aliases": ("技术深度", "技术基础", "实践能力", "实现细节", "technical depth", "technical fundamentals", "implementation", "hands-on")},
    {"id": "design", "label": "方案取舍或系统设计", "aliases": ("系统设计", "方案取舍", "架构", "架构设计", "扩展性", "system design", "trade-off", "tradeoff", "trade off", "architecture", "scalability")},
    {"id": "ops", "label": "故障处理、工程质量或业务理解", "aliases": ("故障", "工程", "质量", "业务理解", "排查", "稳定性", "troubleshooting", "incident", "engineering", "quality", "business", "reliability")},
)


def assert_required_dimensions(topics: list[dict[str, Any]], *, interview_type: str) -> None:
    buckets = CAMPUS_DIMENSION_BUCKETS if interview_type == "campus" else EXPERIENCED_DIMENSION_BUCKETS
    label = "校招" if interview_type == "campus" else "社招"
    for bucket in buckets:
        if not any(_topic_matches_bucket(topic, bucket) for topic in topics):
            raise PlanValidationError(f"{label}必须维度未覆盖: {bucket['label']}")


def _topic_matches_bucket(topic: dict[str, Any], bucket: dict[str, Any]) -> bool:
    haystack = _topic_haystack(topic)
    return any(alias.casefold() in haystack for alias in bucket["aliases"])


def _topic_haystack(topic: dict[str, Any]) -> str:
    parts = [
        str(topic.get("name", "")),
        str(topic.get("dimension", "")),
        " ".join(str(item) for item in topic.get("focus_points", [])),
    ]
    return " ".join(parts).casefold()
