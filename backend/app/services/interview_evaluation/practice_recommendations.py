"""练习建议（06 小步 5）。"""
from __future__ import annotations

from typing import Any

from app.services.interview.memory.signal_map import all_plan_topic_ids, find_plan_topic


FOCUS_TOPIC_OPTIONS = (
    "项目深挖",
    "技术基础",
    "系统设计",
    "业务理解",
    "问题排查",
    "沟通表达",
    "学习能力",
    "算法与编码",
    "Agent 工程能力",
    "Prompt 设计",
)

PRACTICE_MAX_CARDS = 5
PRACTICE_MAX_ACTIONS_PER_CARD = 2

FOCUS_TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "项目深挖": ("项目", "深挖", "经历", "贡献"),
    "系统设计": ("系统设计", "架构", "方案", "高并发", "微服务", "分布式"),
    "Agent 工程能力": ("Agent", "智能体", "工具调用"),
    "Prompt 设计": ("Prompt", "提示词"),
    "算法与编码": ("算法", "编码", "数据结构"),
    "问题排查": ("排查", "故障", "稳定性", "监控", "日志"),
    "业务理解": ("业务", "产品", "需求", "领域"),
    "沟通表达": ("沟通", "表达", "协作", "推进"),
    "学习能力": ("学习", "成长", "校招"),
    "技术基础": ("基础", "原理", "语法", "框架", "Java", "Spring", "Python"),
}


def build_practice_recommendations(
    *,
    plan_json: dict[str, Any],
    competencies: list[dict[str, Any]],
    question_reviews: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    competency_by_topic = {str(item.get("topic_id", "")): item for item in competencies}
    review_by_topic = {str(item.get("topic_id", "")): item for item in question_reviews}
    topic_recommendations: list[dict[str, Any]] = []

    for topic_id in all_plan_topic_ids(plan_json):
        topic = find_plan_topic(plan_json, topic_id)
        if not topic:
            continue
        competency = competency_by_topic.get(topic_id, {})
        review = review_by_topic.get(topic_id, {})
        priority = _derive_priority(competency)
        if priority is None:
            continue

        focus_topic = map_topic_to_focus_topic(
            topic_name=str(topic.get("name") or ""),
            dimension=str(topic.get("dimension") or ""),
        )
        practice_points = list(review.get("practice_points") or [])
        suggested_actions = practice_points[:PRACTICE_MAX_ACTIONS_PER_CARD] if practice_points else [
            f"围绕「{topic.get('name', '')}」准备 2 分钟结构化自我介绍式回答。"
        ]

        topic_recommendations.append(
            {
                "id": topic_id,
                "title": f"加强「{topic.get('name', '')}」",
                "focus_topic": focus_topic,
                "topic_id": topic_id,
                "topic_name": str(topic.get("name") or topic_id),
                "priority": priority,
                "reason": _build_reason(competency=competency),
                "summary": _build_topic_summary(
                    competency=competency,
                    suggested_actions=suggested_actions,
                ),
                "suggested_actions": suggested_actions,
            }
        )

    merged = _merge_by_focus_topic(topic_recommendations)
    merged.sort(key=lambda item: 0 if item["priority"] == "high" else 1)
    return merged[:PRACTICE_MAX_CARDS]


def map_topic_to_focus_topic(*, topic_name: str, dimension: str) -> str:
    haystack = f"{topic_name} {dimension}"
    for focus_topic, keywords in FOCUS_TOPIC_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            return focus_topic
    if topic_name in FOCUS_TOPIC_OPTIONS:
        return topic_name
    return "技术基础"


def _merge_by_focus_topic(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for item in items:
        focus_topic = str(item.get("focus_topic", "")).strip()
        if not focus_topic:
            continue

        group = groups.get(focus_topic)
        if group is None:
            groups[focus_topic] = {
                "id": f"focus-{focus_topic}",
                "title": f"加强「{focus_topic}」",
                "focus_topic": focus_topic,
                "topic_id": item["topic_id"],
                "topic_name": item["topic_name"],
                "topic_ids": [item["topic_id"]],
                "topic_names": [item["topic_name"]],
                "priority": item["priority"],
                "reason": item["reason"],
                "summary": item.get("summary", ""),
                "suggested_actions": list(item.get("suggested_actions") or []),
            }
            continue

        group["topic_ids"].append(item["topic_id"])
        group["topic_names"].append(item["topic_name"])
        if item["priority"] == "high" and group["priority"] != "high":
            group["priority"] = "high"
            group["topic_id"] = item["topic_id"]
            group["topic_name"] = item["topic_name"]
            group["reason"] = item["reason"]
            group["summary"] = item.get("summary", "")
        _merge_suggested_actions(group, item.get("suggested_actions") or [])

    merged: list[dict[str, Any]] = []
    for group in groups.values():
        topic_names = [str(name).strip() for name in group.get("topic_names") or [] if str(name).strip()]
        group["suggested_actions"] = list(group.get("suggested_actions") or [])[:PRACTICE_MAX_ACTIONS_PER_CARD]
        if len(topic_names) > 1:
            group["summary"] = _build_merged_summary(suggested_actions=group["suggested_actions"])
        elif not str(group.get("summary", "")).strip():
            group["summary"] = _build_merged_summary(suggested_actions=group["suggested_actions"])
        merged.append(group)
    return merged


def _merge_suggested_actions(group: dict[str, Any], actions: list[Any]) -> None:
    merged_actions = list(group.get("suggested_actions") or [])
    seen = set(merged_actions)
    for action in actions:
        text = str(action).strip()
        if not text or text in seen or len(merged_actions) >= PRACTICE_MAX_ACTIONS_PER_CARD:
            continue
        seen.add(text)
        merged_actions.append(text)
    group["suggested_actions"] = merged_actions


def _derive_priority(competency: dict[str, Any]) -> str | None:
    status = str(competency.get("status", ""))
    score = competency.get("score")
    risks = competency.get("risks") or []

    if status == "unverified":
        return None
    if status == "partially_verified":
        return "high" if risks else "medium"
    if isinstance(score, int) and score <= 3:
        return "high"
    if risks:
        return "medium"
    return None


def _build_topic_summary(*, competency: dict[str, Any], suggested_actions: list[str]) -> str:
    gap = _primary_gap(competency)
    action = _normalize_practice_action(suggested_actions)
    return f"{gap}，建议{action}"


def _build_merged_summary(*, suggested_actions: list[str]) -> str:
    action = _normalize_practice_action(suggested_actions)
    return f"相关主题薄弱，建议{action}"


def _primary_gap(competency: dict[str, Any]) -> str:
    risks = competency.get("risks") or []
    for item in risks:
        label = str(item).split("—", 1)[0].split("-", 1)[0].strip()
        if label:
            return f"「{label}」仍薄弱"
    status = str(competency.get("status", ""))
    score = competency.get("score")
    if status == "partially_verified":
        return "回答不够完整"
    if isinstance(score, int) and score <= 3:
        return "论证偏弱"
    return "仍有提升空间"


def _normalize_practice_action(suggested_actions: list[str]) -> str:
    raw = str(suggested_actions[0]).strip() if suggested_actions else "准备 2 分钟结构化回答"
    raw = raw.rstrip("。. ")
    if raw.startswith("围绕「") and "」" in raw:
        tail = raw.split("」", 1)[1].strip()
        if tail:
            raw = tail
    return raw


def _build_reason(*, competency: dict[str, Any]) -> str:
    status = str(competency.get("status", ""))
    score = competency.get("score")
    if status == "unverified":
        return "该主题尚未形成足够证据，建议优先补强。"
    if status == "partially_verified":
        return "该主题已有部分证据，但仍存在遗漏信号或风险。"
    if isinstance(score, int) and score <= 3:
        return f"该主题已有评分（{score}/5），仍有明显提升空间。"
    if competency.get("risks"):
        return "该主题存在需要留意的风险点，建议针对性练习。"
    return "建议继续巩固该主题表现。"
