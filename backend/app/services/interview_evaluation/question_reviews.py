"""逐题复盘（06 小步 4）。"""
from __future__ import annotations

from typing import Any

from app.services.interview.memory.signal_map import all_plan_topic_ids, find_plan_topic, plan_signals_for_topic


def build_question_reviews(
    *,
    plan_json: dict[str, Any],
    evaluation_context: dict[str, Any],
    competencies: list[dict[str, Any]],
    runtime_state: dict[str, Any],
) -> list[dict[str, Any]]:
    evidence_by_topic = evaluation_context.get("evidence_by_topic") or {}
    messages_by_topic = evaluation_context.get("messages_by_topic") or {}
    competency_by_topic = {str(item.get("topic_id", "")): item for item in competencies}
    completed_topic_ids = {str(item) for item in (runtime_state.get("completed_topic_ids") or [])}
    reviews: list[dict[str, Any]] = []

    for topic_id in all_plan_topic_ids(plan_json):
        topic = find_plan_topic(plan_json, topic_id)
        if not topic:
            continue
        competency = competency_by_topic.get(topic_id, {})
        bucket = evidence_by_topic.get(topic_id) or {}
        evidence = [item for item in (bucket.get("evidence") or []) if isinstance(item, dict)]
        missing_signals = list(bucket.get("missing_signals") or [])
        messages = messages_by_topic.get(topic_id) or []

        effective_points = _build_effective_points(competency=competency, evidence=evidence, messages=messages)
        gaps_and_risks = _build_gaps_and_risks(
            topic=topic,
            competency=competency,
            missing_signals=missing_signals,
            completed=topic_id in completed_topic_ids,
        )
        organization_tips = _build_organization_tips(
            competency=competency,
            missing_signals=missing_signals,
            topic=topic,
        )
        practice_points = _build_practice_points(
            competency=competency,
            missing_signals=missing_signals,
            topic=topic,
        )
        evidence_quotes = _collect_evidence_quotes(evidence=evidence, messages=messages)

        reviews.append(
            {
                "topic_id": topic_id,
                "name": str(topic.get("name") or topic_id),
                "dimension": str(topic.get("dimension") or ""),
                "objective": str(topic.get("objective") or topic.get("evaluation_criteria") or "").strip(),
                "effective_points": effective_points,
                "gaps_and_risks": gaps_and_risks,
                "organization_tips": organization_tips,
                "practice_points": practice_points,
                "evidence_quotes": evidence_quotes,
            }
        )
    return reviews


def validate_question_reviews(reviews: list[dict[str, Any]], *, plan_json: dict[str, Any]) -> None:
    plan_topics = plan_json.get("topics") or []
    if len(reviews) != len(plan_topics):
        raise ValueError("question_reviews 数量必须与 plan 主题一致")
    for index, review in enumerate(reviews):
        topic = plan_topics[index]
        topic_id = str(topic.get("id", ""))
        if str(review.get("topic_id", "")) != topic_id:
            raise ValueError(f"question_review topic_id 不匹配: {review.get('topic_id')}")
        if str(review.get("name", "")) != str(topic.get("name", "")):
            raise ValueError(f"question_review name 不匹配: {topic_id}")


def _build_effective_points(
    *,
    competency: dict[str, Any],
    evidence: list[dict[str, Any]],
    messages: list[dict[str, Any]],
) -> list[str]:
    points: list[str] = []
    for item in competency.get("strengths") or []:
        text = str(item).strip()
        if text and text not in points:
            points.append(text)
    for item in evidence:
        if str(item.get("polarity", "")) != "positive":
            continue
        quote = str(item.get("quote", "")).strip()
        signal = str(item.get("matched_signal", "")).strip()
        if not quote:
            continue
        label = f"{signal}：{quote}" if signal else quote
        if label not in points:
            points.append(label)
    if not points:
        for message in messages:
            if str(message.get("role", "")) != "user":
                continue
            content = str(message.get("content", "")).strip()
            if len(content) >= 12 and content not in points:
                points.append(content[:160])
            if len(points) >= 2:
                break
    return points[:4]


def _build_gaps_and_risks(
    *,
    topic: dict[str, Any],
    competency: dict[str, Any],
    missing_signals: list[str],
    completed: bool,
) -> list[str]:
    gaps: list[str] = []
    for signal in missing_signals:
        text = f"尚未覆盖考察信号：{signal}"
        if text not in gaps:
            gaps.append(text)
    for item in competency.get("risks") or []:
        text = str(item).strip()
        if text and text not in gaps:
            gaps.append(text)
    status = str(competency.get("status", ""))
    if status == "unverified":
        if completed:
            gaps.append("该主题已讨论，但缺少可引用证据支撑结论。")
        else:
            gaps.append("该主题尚未充分讨论或未形成有效证据。")
    elif status == "partially_verified" and missing_signals:
        gaps.append(f"建议补充与「{topic.get('name', '')}」相关的关键细节。")
    return gaps[:4]


def _build_organization_tips(
    *,
    competency: dict[str, Any],
    missing_signals: list[str],
    topic: dict[str, Any],
) -> list[str]:
    status = str(competency.get("status", ""))
    tips: list[str] = []
    if status == "unverified":
        tips.append("先用一句话给出结论，再按背景-行动-结果展开，避免只罗列名词。")
    elif status == "partially_verified":
        tips.append("在现有回答基础上，优先补齐遗漏考察点，再补充量化结果与个人贡献。")
    else:
        tips.append("保持结论先行，并补充 1 个备选方案或边界情况，体现取舍思考。")

    if missing_signals:
        tips.append(f"针对遗漏信号「{'、'.join(missing_signals[:2])}」各准备 1 条可引用事实。")

    criteria = str(topic.get("evaluation_criteria", "")).strip()
    if criteria:
        tips.append(f"对照考察标准组织回答：{criteria}")
    return tips[:3]


def _build_practice_points(
    *,
    competency: dict[str, Any],
    missing_signals: list[str],
    topic: dict[str, Any],
) -> list[str]:
    points: list[str] = []
    topic_name = str(topic.get("name") or "")
    status = str(competency.get("status", ""))
    score = competency.get("score")

    if status == "unverified":
        points.append(f"复盘「{topic_name}」相关项目/经历，准备 2 条可量化的事实。")
    elif status == "partially_verified":
        points.append(f"围绕「{topic_name}」补齐 {len(missing_signals) or 1} 个遗漏考察点的回答要点。")
    elif isinstance(score, int) and score <= 3:
        points.append(f"重新梳理「{topic_name}」回答结构，突出个人决策与结果指标。")
    else:
        points.append(f"巩固「{topic_name}」现有优势，并准备 1 个反例或失败复盘。")

    for signal in missing_signals[:2]:
        points.append(f"专项练习：如何清晰说明「{signal}」。")
    return points[:3]


def _collect_evidence_quotes(*, evidence: list[dict[str, Any]], messages: list[dict[str, Any]]) -> list[str]:
    quotes: list[str] = []
    for item in evidence:
        quote = str(item.get("quote", "")).strip()
        if quote and quote not in quotes:
            quotes.append(quote)
    if not quotes:
        for message in messages:
            if str(message.get("role", "")) != "user":
                continue
            content = str(message.get("content", "")).strip()
            if content and content not in quotes:
                quotes.append(content[:160])
            if len(quotes) >= 3:
                break
    return quotes[:4]
