"""候选人可读报告层（06 补：报告可读性）。"""
from __future__ import annotations

from typing import Any


from app.services.interview.memory.merge import EVIDENCE_COVERAGE_MIN_STRENGTH
from app.services.interview_evaluation.aggregate import is_partial_score_coverage
from app.services.interview_evaluation.feedback_items import (
    feedback_item_key,
    feedback_item_text,
    make_feedback_item,
)


from app.services.interview_evaluation.presentation import resolve_competency_status_label

_HIGHLIGHT_SKIP_MARKERS = (
    "优势证据仍不足",
    "已有回答记录",
    "可在后续版本",
    "表现优秀",
    "非常出色",
    "非常棒",
)


def build_score_coverage_context(
    *,
    scored_topic_count: int,
    total_topic_count: int,
    completed_topic_count: int | None = None,
    discussed_topic_count: int | None = None,
) -> dict[str, str]:
    if total_topic_count <= 0:
        return {"coverage_note": "", "overall_score_label": "综合得分"}

    is_partial = is_partial_score_coverage(
        scored_topic_count=scored_topic_count,
        total_topic_count=total_topic_count,
    )
    if not is_partial:
        return {
            "coverage_note": f"本场计划 {total_topic_count} 个考察点，均已纳入综合分。",
            "overall_score_label": "综合得分",
        }

    unscored = total_topic_count - scored_topic_count
    discussed = discussed_topic_count
    if discussed is None:
        discussed = scored_topic_count
    else:
        discussed = max(discussed, scored_topic_count)
    return {
        "coverage_note": (
            f"本场计划 {total_topic_count} 个考察点，你聊到 {discussed} 个，"
            f"其中 {scored_topic_count} 个已有评分。"
            f"综合分仅反映已评分内容，其余 {unscored} 个因讨论不足未计入，不代表能力不足。"
        ),
        "overall_score_label": "已评考察点均分",
    }


def build_candidate_review(
    *,
    competencies: list[dict[str, Any]],
    question_reviews: list[dict[str, Any]],
    practice_recommendations: list[dict[str, Any]],
    overall_score: int | None,
    risks: list[str],
    unverified_items: list[dict[str, Any]],
    configuration: dict[str, Any],
    strengths: list[str] | None = None,
    completed_topic_count: int | None = None,
    total_topic_count: int | None = None,
    scored_topic_count: int | None = None,
    discussed_topic_count: int | None = None,
    plan_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    interview_type = str(configuration.get("interview_type", "experienced"))
    audience = "校招" if interview_type == "campus" else "社招"

    weaknesses = _build_weaknesses(
        competencies=competencies,
        risks=risks,
    )
    highlights = _build_highlights(competencies=competencies)
    suggestions = _build_suggestions(
        practice_recommendations=practice_recommendations,
        question_reviews=question_reviews,
        competencies=competencies,
    )
    summary = _build_candidate_summary(
        audience=audience,
        competencies=competencies,
        overall_score=overall_score,
        weaknesses=weaknesses,
        suggestions=suggestions,
        strengths=strengths or [],
        completed_topic_count=completed_topic_count,
        total_topic_count=total_topic_count,
        scored_topic_count=scored_topic_count,
        plan_json=plan_json,
        unverified_items=unverified_items,
    )
    headline = _build_headline(
        overall_score=overall_score,
        competencies=competencies,
        completed_topic_count=completed_topic_count,
        total_topic_count=total_topic_count,
        scored_topic_count=scored_topic_count,
    )
    coverage_context = build_score_coverage_context(
        scored_topic_count=scored_topic_count or 0,
        total_topic_count=total_topic_count or 0,
        completed_topic_count=completed_topic_count,
        discussed_topic_count=discussed_topic_count,
    )

    return {
        "headline": headline,
        "summary": summary,
        "highlights": highlights[:3],
        "weaknesses": weaknesses[:5],
        "suggestions": suggestions[:5],
        "coverage_note": coverage_context["coverage_note"],
        "overall_score_label": coverage_context["overall_score_label"],
    }


def enrich_competencies_for_candidate(
    competencies: list[dict[str, Any]],
    *,
    question_reviews: list[dict[str, Any]] | None = None,
    agent_comments: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    review_by_topic = {
        str(item.get("topic_id", "")): item for item in (question_reviews or []) if isinstance(item, dict)
    }
    agent_comments = agent_comments or {}
    enriched: list[dict[str, Any]] = []
    for competency in competencies:
        item = dict(competency)
        topic_id = str(item.get("topic_id", ""))
        agent_comment = str(agent_comments.get(topic_id, "")).strip()
        item["evaluation_comment"] = agent_comment or _build_competency_comment(
            item,
            review=review_by_topic.get(topic_id),
        )
        enriched.append(item)
    return enriched


def _build_headline(
    *,
    overall_score: int | None,
    competencies: list[dict[str, Any]],
    completed_topic_count: int | None = None,
    total_topic_count: int | None = None,
    scored_topic_count: int | None = None,
) -> str:
    scored = scored_topic_count if scored_topic_count is not None else sum(
        1 for item in competencies if item.get("score") is not None
    )
    total = total_topic_count or len(competencies)
    partial = is_partial_score_coverage(scored_topic_count=scored, total_topic_count=total)

    if overall_score is not None:
        if partial:
            if overall_score >= 80:
                return "已讨论的考察点表现较好，建议补练未覆盖主题"
            if overall_score >= 60:
                return "已讨论的考察点表现中等，仍有未覆盖环节待加强"
            if overall_score >= 40:
                return "已讨论的考察点表现一般，建议补练未覆盖主题"
            return "已讨论的考察点表现偏弱，建议系统复盘并针对性练习"

        if overall_score >= 80:
            return "整体表现较好，多数考察点回答到位"
        if overall_score >= 60:
            return "整体表现中等，仍有明显提升空间"
        if overall_score >= 40:
            return "整体表现一般，多个环节需要加强"
        return "整体表现偏弱，建议系统复盘并针对性练习"

    if not competencies and total_topic_count:
        completed = completed_topic_count or 0
        if completed == 0:
            return "本场有效回答较少，暂难形成完整评价"
        if completed < total_topic_count:
            return "部分考察点已有回答，仍有环节需要加强"
        return "已完成本场模拟面试，请查看反馈详情"

    unverified_count = sum(1 for item in competencies if item.get("status") == "unverified")
    if unverified_count == len(competencies) and competencies:
        return "本场有效回答较少，暂难形成完整评价"
    if unverified_count > 0:
        return "部分考察点尚未充分展开，评价以已讨论内容为准"
    return "已完成本场模拟面试，请查看各维度反馈"


def _build_candidate_summary(
    *,
    audience: str,
    competencies: list[dict[str, Any]],
    overall_score: int | None,
    weaknesses: list[dict[str, str]],
    suggestions: list[dict[str, str]],
    strengths: list[str],
    completed_topic_count: int | None = None,
    total_topic_count: int | None = None,
    scored_topic_count: int | None = None,
    plan_json: dict[str, Any] | None = None,
    unverified_items: list[dict[str, Any]] | None = None,
) -> str:
    scored_count = scored_topic_count if scored_topic_count is not None else sum(
        1 for item in competencies if item.get("score") is not None
    )
    total = total_topic_count or len(competencies)
    partial = is_partial_score_coverage(scored_topic_count=scored_count, total_topic_count=total)
    scored_competencies = [item for item in competencies if item.get("score") is not None]
    strong_topics = [str(item.get("name", "")) for item in scored_competencies if int(item.get("score") or 0) >= 4]
    weak_topics = _performance_weak_topic_names(competencies)

    parts = [f"这是一场{audience}模拟面试的反馈。"]
    if total_topic_count and completed_topic_count is not None:
        parts.append(f"本次共 {total_topic_count} 个考察点，你充分展开了其中 {completed_topic_count} 个。")
    if overall_score is not None:
        if partial and total > 0:
            unscored = total - scored_count
            parts.append(
                f"在已评分的 {scored_count} 个考察点上，均分约 {overall_score} 分（满分 100）；"
                f"其余 {unscored} 个考察点因讨论不足未计入综合分。"
            )
        else:
            parts.append(f"综合表现约 {overall_score} 分（满分 100）。")
    elif scored_competencies:
        parts.append("部分考察点已有评分，其余内容因讨论不足暂未给出确定结论。")
    elif not total_topic_count:
        parts.append("由于有效回答或证据不足，本场未给出综合分数。")

    if strong_topics:
        parts.append(f"相对较好的环节包括：{'、'.join(strong_topics[:3])}。")
    elif strengths:
        parts.append(f"回答中的亮点包括：{'、'.join(strengths[:2])}。")
    if weak_topics:
        parts.append(f"需要重点留意的环节包括：{'、'.join(weak_topics[:3])}。")
    if weaknesses:
        parts.append(f"主要问题：{feedback_item_text(weaknesses[0])}")
    if suggestions:
        parts.append(f"建议下一步：{feedback_item_text(suggestions[0])}")
    return "".join(parts)


def _build_weaknesses(
    *,
    competencies: list[dict[str, Any]],
    risks: list[str],
) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def append_item(*, title: str, body: str) -> None:
        item = make_feedback_item(title=title, body=body)
        key = feedback_item_key(item)
        if key in seen:
            return
        seen.add(key)
        items.append(item)

    for competency in competencies:
        name = str(competency.get("name", "")).strip()
        score = competency.get("score")
        if isinstance(score, int) and score <= 3 and name:
            append_item(title=name, body="回答深度不够，关键考察点尚未讲清楚。")
        for risk in competency.get("risks") or []:
            text = _plain_text(str(risk))
            if not text:
                continue
            title = _weakness_title_from_risk(text, fallback=name or "待加强点")
            append_item(title=title, body=text)
    for risk in risks:
        text = _plain_text(str(risk))
        if not text:
            continue
        append_item(title=_weakness_title_from_risk(text, fallback="表述一致性"), body=text)
    return items


def _competency_has_performance_gap(competency: dict[str, Any]) -> bool:
    status = str(competency.get("status", ""))
    if status == "unverified":
        return False
    score = competency.get("score")
    if isinstance(score, int) and score <= 3:
        return True
    if competency.get("risks"):
        return True
    if status == "partially_verified":
        return True
    return False


def _performance_weak_topic_names(competencies: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for competency in competencies:
        if not _competency_has_performance_gap(competency):
            continue
        name = str(competency.get("name", "")).strip()
        if name and name not in names:
            names.append(name)
    return names


def _build_suggestions(
    *,
    practice_recommendations: list[dict[str, Any]],
    question_reviews: list[dict[str, Any]],
    competencies: list[dict[str, Any]],
) -> list[dict[str, str]]:
    competency_by_topic = {str(item.get("topic_id", "")): item for item in competencies}
    items: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def append_item(*, title: str, body: str) -> None:
        item = make_feedback_item(title=title, body=body)
        key = feedback_item_key(item)
        if key in seen:
            return
        seen.add(key)
        items.append(item)

    for recommendation in practice_recommendations:
        topic_id = str(recommendation.get("topic_id", "")).strip()
        competency = competency_by_topic.get(topic_id, {})
        if not _competency_has_performance_gap(competency):
            continue
        action = (recommendation.get("suggested_actions") or [None])[0]
        focus_topic = str(recommendation.get("focus_topic", "")).strip()
        title = str(recommendation.get("title", "")).strip() or focus_topic or str(competency.get("name", "")).strip()
        if isinstance(action, str) and action.strip():
            append_item(title=title or "针对性练习", body=action.strip())
        elif title:
            append_item(
                title=title,
                body="准备 2 分钟结构化回答，并补充量化结果与个人贡献。",
            )
        elif focus_topic:
            append_item(title=focus_topic, body="下次练习可将该方向作为重点，准备可引用的事实与数据。")

    review_by_topic = {str(item.get("topic_id", "")): item for item in question_reviews}
    for competency in competencies:
        if not _competency_has_performance_gap(competency):
            continue
        name = str(competency.get("name", "")).strip() or "回答组织"
        review = review_by_topic.get(str(competency.get("topic_id", ""))) or {}
        tip = (review.get("organization_tips") or [None])[0]
        if isinstance(tip, str) and tip.strip():
            append_item(title=f"{name}表达", body=tip.strip())

    return items[:5]


def _build_competency_comment(competency: dict[str, Any], *, review: dict[str, Any] | None) -> str:
    name = str(competency.get("name", "")).strip()
    status = str(competency.get("status", ""))
    score = competency.get("score")
    status_label = resolve_competency_status_label(status, score if isinstance(score, int) else None)

    if status == "unverified":
        gap = (review or {}).get("gaps_and_risks") or []
        if gap:
            return f"「{name}」{status_label}。{gap[0]}"
        return f"「{name}」{status_label}，建议用具体项目或数据补充说明。"

    parts = [f"「{name}」{status_label}"]

    highlight = _first_plain_highlight(competency)
    if highlight and not (isinstance(score, int) and score <= 2):
        parts.append(f"有效信息：{highlight}")

    gap = (review or {}).get("gaps_and_risks") or competency.get("risks") or []
    if gap:
        parts.append(f"待改进：{_plain_text(str(gap[0]))}")

    tip = (review or {}).get("organization_tips") or []
    if tip:
        parts.append(f"建议：{_plain_text(str(tip[0]))}")

    return "。".join(parts[:3]) + ("。" if parts else "")


def _first_plain_highlight(competency: dict[str, Any]) -> str:
    for item in competency.get("strengths") or []:
        text = _plain_text(str(item))
        if text:
            return text
    for item in competency.get("evidence_references") or []:
        if isinstance(item, dict):
            quote = str(item.get("quote", "")).strip()
            if quote:
                return quote
    return ""


def _build_highlights(*, competencies: list[dict[str, Any]]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def append_item(*, title: str, body: str) -> None:
        item = make_feedback_item(title=title, body=body)
        key = feedback_item_key(item)
        if key in seen:
            return
        seen.add(key)
        items.append(item)

    ordered = sorted(
        competencies,
        key=lambda item: (
            0 if item.get("status") == "verified" else 1 if item.get("status") == "partially_verified" else 2,
            -(int(item.get("score") or 0)),
        ),
    )

    for competency in ordered:
        status = str(competency.get("status", ""))
        if status == "unverified":
            continue
        name = str(competency.get("name", "")).strip()
        if not name:
            continue

        for reference in competency.get("evidence_references") or []:
            if not isinstance(reference, dict):
                continue
            if str(reference.get("polarity", "")) != "positive":
                continue
            try:
                strength = float(reference.get("strength", 0) or 0)
            except (TypeError, ValueError):
                strength = 0.0
            if strength < EVIDENCE_COVERAGE_MIN_STRENGTH:
                continue
            quote = _truncate_quote(str(reference.get("quote", "")).strip())
            signal = str(reference.get("matched_signal", "")).strip()
            if not quote:
                continue
            title, body = _format_highlight(name=name, signal=signal, quote=quote, status=status)
            append_item(title=title, body=body)
            if len(items) >= 3:
                return items

        for raw in competency.get("strengths") or []:
            parsed = _highlight_from_competency_strength(name=name, raw=str(raw))
            if parsed:
                append_item(title=parsed["title"], body=parsed["body"])
            if len(items) >= 3:
                return items

    return items[:3]


def _format_highlight(*, name: str, signal: str, quote: str, status: str) -> tuple[str, str]:
    focus = signal or "关键细节"
    title = name or focus
    if status == "verified":
        body = f"关于{focus}，你提到「{quote}」，这一点讲得比较清楚。"
    else:
        body = f"关于{focus}，你提到「{quote}」，方向基本对，细节还可以再展开。"
    return title, body


def _highlight_from_competency_strength(*, name: str, raw: str) -> dict[str, str] | None:
    text = _plain_text(raw)
    if not text or any(marker in text for marker in _HIGHLIGHT_SKIP_MARKERS):
        return None
    if text.startswith("「") and "」" in text:
        legacy = text
        bracket_match = legacy.split("」", 1)
        title = bracket_match[0].lstrip("「").strip() or name
        body = bracket_match[1].strip() or legacy
        return make_feedback_item(title=title, body=body)
    if " — " in raw:
        signal, quote = raw.split(" — ", 1)
        signal = signal.strip()
        quote = _truncate_quote(quote.strip())
        if quote:
            return make_feedback_item(
                title=name or signal or "回答亮点",
                body=f"你提到「{quote}」，这一点有一定可取之处。",
            )
    if len(text) >= 8:
        return make_feedback_item(title=name or "回答亮点", body=text)
    return None


def _weakness_title_from_risk(text: str, *, fallback: str) -> str:
    if text.startswith("尚未覆盖考察信号："):
        signal = text.removeprefix("尚未覆盖考察信号：").strip()
        if signal:
            return signal[:16]
    if " — " in text:
        signal = text.split(" — ", 1)[0].strip()
        if signal:
            return signal[:16]
    return fallback[:16] or "待加强点"


def _truncate_quote(quote: str, max_len: int = 52) -> str:
    if len(quote) <= max_len:
        return quote
    return quote[: max_len - 1].rstrip() + "…"


def _plain_text(value: str) -> str:
    text = value.strip()
    if " — " in text:
        text = text.split(" — ", 1)[-1].strip()
    if "：" in text:
        left, right = text.split("：", 1)
        if len(right.strip()) >= 8:
            text = right.strip()
        elif len(left) <= 12:
            text = right.strip() or text
    return text
