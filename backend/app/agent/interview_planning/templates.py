"""Planning 模板降级：LLM 调用失败时，基于规则生成可校验的兜底计划。"""
from typing import Any

from app.services.interview_planning.constants import PLAN_BOUNDARIES
from app.services.interview_planning.regeneration import apply_regeneration_to_plan


def build_template_fallback_plan(
    *,
    configuration: dict[str, Any],
    resume: dict[str, Any],
    role_knowledge_context: str = "",
    regeneration_feedback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _ = role_knowledge_context
    interview_type = configuration["interview_type"]
    focus_topics = configuration["focus_topics"]
    jd_text = configuration.get("jd_text", "")
    has_jd = bool(jd_text.strip())
    target_role = configuration.get("target_role", "backend")
    target_level = configuration.get("target_level", "intermediate")

    if interview_type == "campus":
        topics = _campus_topics(focus_topics, target_role=target_role, target_level=target_level)
        reference_summary = _campus_reference_summary(resume, has_jd, jd_text)
    else:
        topics = _experienced_topics(focus_topics, target_role=target_role, target_level=target_level)
        reference_summary = _experienced_reference_summary(resume, has_jd, jd_text)

    plan = {
        **PLAN_BOUNDARIES,
        "topics": topics,
        "candidate_summary": {
            "focus_topics": list(configuration.get("focus_topics", focus_topics)),
            "reference_summary": reference_summary,
        },
        "source": "template_fallback",
        "generation_attempts": 0,
        "degraded": True,
    }
    if regeneration_feedback:
        plan = apply_regeneration_to_plan(
            plan,
            regeneration_feedback=regeneration_feedback,
            configuration=configuration,
        )
    return plan


def build_demo_plan(
    *,
    configuration: dict[str, Any],
    resume: dict[str, Any],
    role_knowledge_context: str = "",
) -> dict[str, Any]:
    return build_template_fallback_plan(
        configuration=configuration,
        resume=resume,
        role_knowledge_context=role_knowledge_context,
    )


def _experienced_topics(focus_topics: list[str], *, target_role: str, target_level: str) -> list[dict[str, Any]]:
    _ = target_level
    primary_focus = focus_topics[0] if focus_topics else "项目深挖"
    secondary_focus = focus_topics[1] if len(focus_topics) > 1 else "技术基础"
    role_topic_name = {
        "frontend": "前端工程化",
        "backend": "技术深度",
        "fullstack": "全栈协同",
        "agent": "Agent 工程能力",
    }.get(target_role, "技术深度")
    return [
        _topic(
            "topic-1",
            "项目所有权",
            "项目经历真实性验证",
            ["核心项目", "个人职责边界"],
            required=True,
            minutes=8,
            focus_hint=primary_focus,
        ),
        _topic(
            "topic-2",
            role_topic_name,
            "技术深度",
            [secondary_focus, "关键实现细节"],
            required=True,
            minutes=8,
        ),
        _topic(
            "topic-3",
            "系统设计",
            "方案取舍或系统设计",
            ["架构取舍", "扩展性与稳定性"],
            required=True,
            minutes=8,
        ),
        _topic(
            "topic-4",
            "故障处理",
            "故障处理",
            ["线上问题", "排查与复盘"],
            required=True,
            minutes=7,
        ),
        _topic(
            "topic-5",
            "业务理解",
            "业务理解",
            ["业务目标", "技术价值对齐"],
            required=False,
            minutes=7,
        ),
    ]


def _campus_topics(focus_topics: list[str], *, target_role: str, target_level: str) -> list[dict[str, Any]]:
    _ = (target_role, target_level)
    primary_focus = focus_topics[0] if focus_topics else "学习能力"
    return [
        _topic(
            "topic-1",
            "技术基础",
            "技术或专业基础",
            [primary_focus, "语言与数据结构"],
            required=True,
            minutes=8,
        ),
        _topic(
            "topic-2",
            "项目与实习",
            "项目、实习或竞赛经历",
            ["项目职责", "个人贡献"],
            required=True,
            minutes=8,
        ),
        _topic(
            "topic-3",
            "问题分析",
            "问题分析能力",
            ["拆解思路", "边界条件"],
            required=True,
            minutes=8,
        ),
        _topic(
            "topic-4",
            "学习能力",
            "学习能力或成长潜力",
            ["学习方法", "成长案例"],
            required=True,
            minutes=7,
        ),
        _topic(
            "topic-5",
            "沟通表达",
            "沟通表达",
            ["表达清晰度", "协作意识"],
            required=False,
            minutes=7,
        ),
    ]


def _topic(
    topic_id: str,
    name: str,
    dimension: str,
    focus_points: list[str],
    *,
    required: bool,
    minutes: int,
    focus_hint: str | None = None,
) -> dict[str, Any]:
    opening_hint = focus_hint or focus_points[0]
    return {
        "id": topic_id,
        "name": name,
        "dimension": dimension,
        "objective": f"围绕{name}验证候选人的{dimension}",
        "focus_points": focus_points,
        "required": required,
        "estimated_minutes": minutes,
        "max_rounds": 3,
        "opening_question": f"请结合你的经历，谈谈在{opening_hint}方面的具体实践。",
        "expected_signals": focus_points[:2],
        "probe_strategies": ["追问具体决策、结果与个人贡献"],
        "evaluation_criteria": f"是否能给出可验证的{name}相关案例",
        "source_refs": ["resume:demo"],
    }


def _experienced_reference_summary(resume: dict[str, Any], has_jd: bool, jd_text: str) -> list[str]:
    project_name = _first_project_name(resume)
    summaries = []
    if project_name:
        summaries.append(f"将重点参考「{project_name}」及相关工作经历")
    else:
        summaries.append("将重点参考简历中的核心项目与技术栈")
    if has_jd:
        summaries.append(f"已结合 JD 中的关键要求（{_jd_hint(jd_text)}）")
    else:
        summaries.append("未提供 JD，按岗位通用模式组织考察方向")
    return summaries


def _campus_reference_summary(resume: dict[str, Any], has_jd: bool, jd_text: str) -> list[str]:
    project_name = _first_project_name(resume)
    summaries = []
    if project_name:
        summaries.append(f"将重点参考「{project_name}」及校园/实习经历")
    else:
        summaries.append("将重点参考简历中的学习、项目与实习经历")
    if has_jd:
        summaries.append(f"已结合 JD 中的培养方向（{_jd_hint(jd_text)}）")
    else:
        summaries.append("未提供 JD，按校招通用模式组织考察方向")
    return summaries


def _first_project_name(resume: dict[str, Any]) -> str:
    projects = resume.get("project_experience") or []
    if not projects:
        return ""
    first = projects[0]
    if isinstance(first, dict):
        return str(first.get("name") or first.get("title") or "").strip()
    return ""


def _jd_hint(jd_text: str) -> str:
    compact = " ".join(jd_text.split())
    if len(compact) <= 24:
        return compact or "岗位关键要求"
    return f"{compact[:24]}..."
