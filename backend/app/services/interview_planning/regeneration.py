"""Planning 重新生成：版本 diff、策略后验、上一版摘要，以及模板降级路径下的微调。"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.agent.interview_planning.validator import PlanValidationError
from app.services.interview_planning.constants import REGENERATION_STRATEGY_LABELS


def build_previous_plan_summary(plan_record: dict[str, Any]) -> dict[str, Any]:
    plan_json = plan_record.get("plan_json", {})
    candidate_summary = plan_record.get("candidate_summary_json", {})
    topics = plan_json.get("topics", [])
    return {
        "version": plan_record.get("version"),
        "topics": [
            {
                "name": topic.get("name"),
                "dimension": topic.get("dimension"),
                "required": topic.get("required"),
                "estimated_minutes": topic.get("estimated_minutes"),
                "focus_points": list(topic.get("focus_points", []))[:4],
            }
            for topic in topics
            if isinstance(topic, dict)
        ],
        "reference_summary": list(candidate_summary.get("reference_summary", [])),
        "focus_topics": list(candidate_summary.get("focus_topics", [])),
    }


def plans_have_effective_difference(previous: dict[str, Any], current: dict[str, Any]) -> bool:
    return _plan_signature(previous) != _plan_signature(current)


def apply_regeneration_to_plan(
    plan: dict[str, Any],
    *,
    regeneration_feedback: dict[str, Any],
    configuration: dict[str, Any],
) -> dict[str, Any]:
    updated = deepcopy(plan)
    strategy = regeneration_feedback["regeneration_strategy"]
    topics = updated.get("topics", [])
    candidate_summary = updated.setdefault("candidate_summary", {})
    reference_summary = list(candidate_summary.get("reference_summary", []))
    label = REGENERATION_STRATEGY_LABELS.get(strategy, strategy)

    if strategy == "align_resume":
        reference_summary.append("重新生成：更聚焦简历核心项目与个人贡献")
        if topics:
            topics[0]["name"] = _rename_topic(topics[0].get("name", ""), "（简历对齐）")
    elif strategy == "align_jd":
        reference_summary.append("重新生成：更贴合 JD 中的岗位要求")
        if len(topics) > 2:
            topics[2]["name"] = _rename_topic(topics[2].get("name", ""), "（JD 对齐）")
    elif strategy == "increase_technical_depth":
        reference_summary.append("重新生成：加强技术深度与实现细节考察")
        if len(topics) > 1:
            topics[1]["name"] = "技术深度强化"
    elif strategy == "increase_fundamentals":
        reference_summary.append("重新生成：加强基础原理与核心概念考察")
        if topics:
            topics[0]["name"] = "基础与原理"
    elif strategy == "increase_practical_cases":
        reference_summary.append("重新生成：加强实战案例与问题排查考察")
        if len(topics) > 3:
            topics[3]["name"] = "实战案例"
    elif strategy == "different_plan":
        reference_summary.append("重新生成：换一套不同排列的考察方向")
        if topics:
            optional = next((topic for topic in topics if not topic.get("required")), topics[-1])
            optional["required"] = True
            optional["name"] = _rename_topic(optional.get("name", ""), "（调整版）")

    additional = str(regeneration_feedback.get("additional_instruction", "") or "").strip()
    if additional and strategy == "different_plan":
        reference_summary.append(f"补充要求：{additional[:120]}")

    reference_summary.append(f"调整策略：{label}")
    candidate_summary["reference_summary"] = _dedupe_strings(reference_summary)
    updated["topics"] = topics
    return updated


def _plan_signature(plan_record: dict[str, Any]) -> tuple[Any, ...]:
    plan_json = plan_record.get("plan_json", {})
    candidate_summary = plan_record.get("candidate_summary_json", {})
    topic_signatures = tuple(
        _topic_content_signature(topic)
        for topic in plan_json.get("topics", [])
        if isinstance(topic, dict)
    )
    reference_summary = tuple(str(item).strip() for item in candidate_summary.get("reference_summary", []))
    focus_topics = tuple(str(item).strip() for item in candidate_summary.get("focus_topics", []))
    return (topic_signatures, reference_summary, focus_topics)


def _topic_content_signature(topic: dict[str, Any]) -> tuple[str, ...]:
    focus_points = tuple(str(item).strip() for item in topic.get("focus_points", []) if str(item).strip())
    opening_question = str(topic.get("opening_question", "")).strip()[:120]
    return (
        str(topic.get("name", "")).strip(),
        str(topic.get("dimension", "")).strip(),
        focus_points,
        opening_question,
    )


def _rename_topic(name: str, suffix: str) -> str:
    base = name.replace("（简历对齐）", "").replace("（JD 对齐）", "").replace("（调整版）", "").strip()
    if suffix.strip("（）") in base:
        return base
    return f"{base}{suffix}"


def _dedupe_strings(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        text = str(item).strip()
        if text and text not in result:
            result.append(text)
    return result


def validate_regeneration_strategy_outcome(
    *,
    plan: dict[str, Any],
    candidate_summary: dict[str, Any],
    configuration: dict[str, Any],
    resume: dict[str, Any],
    regeneration_feedback: dict[str, Any],
    previous_plan_summary: dict[str, Any] | None,
) -> None:
    strategy = regeneration_feedback["regeneration_strategy"]
    topics = plan.get("topics", [])

    if strategy == "align_jd":
        _validate_align_jd(topics, candidate_summary, configuration)
    elif strategy == "align_resume":
        _validate_align_resume(topics, candidate_summary, resume)
    elif strategy == "different_plan":
        _validate_different_plan(topics, previous_plan_summary)


def _validate_align_jd(
    topics: list[dict[str, Any]],
    candidate_summary: dict[str, Any],
    configuration: dict[str, Any],
) -> None:
    jd_text = str(configuration.get("jd_text", "") or "").strip()
    if not jd_text:
        raise PlanValidationError("align_jd 策略需要 JD 文本")

    source_refs = _collect_source_refs(topics)
    references = " ".join(candidate_summary.get("reference_summary", []))
    has_jd_ref = any(ref.lower().startswith("jd:") or ref.lower().startswith("jd：") for ref in source_refs)
    has_jd_hint = _contains_jd_hint(references, jd_text) or _contains_jd_hint(source_refs, jd_text)
    if not (has_jd_ref or has_jd_hint):
        raise PlanValidationError("align_jd 策略要求 reference_summary 或 source_refs 体现 JD 要点")


def _validate_align_resume(
    topics: list[dict[str, Any]],
    candidate_summary: dict[str, Any],
    resume: dict[str, Any],
) -> None:
    source_refs = _collect_source_refs(topics)
    references = " ".join(candidate_summary.get("reference_summary", []))
    has_resume_ref = any(ref.lower().startswith("resume:") or ref.lower().startswith("resume：") for ref in source_refs)
    project_names = _resume_project_names(resume)
    mentions_project = any(name and name in references for name in project_names)
    mentions_project_in_refs = any(name and name in " ".join(source_refs) for name in project_names)
    if not (has_resume_ref or mentions_project or mentions_project_in_refs):
        raise PlanValidationError("align_resume 策略要求 reference_summary 或 source_refs 体现简历项目/经历")


def _validate_different_plan(topics: list[dict[str, Any]], previous_plan_summary: dict[str, Any] | None) -> None:
    if not previous_plan_summary:
        raise PlanValidationError("different_plan 策略需要上一版计划摘要")

    previous_topics = previous_plan_summary.get("topics", [])
    previous_names = [str(item.get("name", "")).strip() for item in previous_topics if isinstance(item, dict)]
    current_names = [str(topic.get("name", "")).strip() for topic in topics if isinstance(topic, dict)]

    name_changes = sum(1 for prev, curr in zip(previous_names, current_names) if prev != curr)
    name_changes += abs(len(previous_names) - len(current_names))

    previous_pairs = {
        (str(item.get("name", "")).strip(), str(item.get("dimension", "")).strip())
        for item in previous_topics
        if isinstance(item, dict)
    }
    current_pairs = {
        (str(topic.get("name", "")).strip(), str(topic.get("dimension", "")).strip())
        for topic in topics
        if isinstance(topic, dict)
    }
    pair_changes = len(previous_pairs.symmetric_difference(current_pairs))

    if name_changes >= 3 or (name_changes >= 2 and pair_changes >= 2):
        return
    raise PlanValidationError(
        "different_plan 策略要求与上一版相比至少 3 个主题 name 不同，"
        "或至少 2 个 name 不同且 2 组 name+dimension 组合变化"
    )


def _collect_source_refs(topics: list[dict[str, Any]]) -> list[str]:
    refs: list[str] = []
    for topic in topics:
        if not isinstance(topic, dict):
            continue
        for ref in topic.get("source_refs", []):
            text = str(ref).strip()
            if text:
                refs.append(text)
    return refs


def _resume_project_names(resume: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for key in ("project_experience", "work_experience"):
        for item in resume.get(key) or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("title") or "").strip()
            if name and name not in names:
                names.append(name)
    return names


def _contains_jd_hint(text: str | list[str], jd_text: str) -> bool:
    if isinstance(text, list):
        joined = " ".join(str(item) for item in text)
    else:
        joined = str(text)
    compact_jd = " ".join(jd_text.split())
    if not compact_jd:
        return False
    if compact_jd[:12] in joined:
        return True
    for token in _significant_tokens(compact_jd):
        if token in joined:
            return True
    return False


def _significant_tokens(text: str) -> list[str]:
    tokens = []
    for part in text.replace("，", " ").replace("。", " ").split():
        token = part.strip()
        if len(token) >= 2 and token not in tokens:
            tokens.append(token)
    return tokens[:6]
