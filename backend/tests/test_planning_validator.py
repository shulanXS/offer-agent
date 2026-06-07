import pytest

from app.agent.interview_planning.validator import PlanValidationError, validate_and_normalize_plan
from app.agent.interview_planning.templates import build_template_fallback_plan


def _base_configuration(**overrides: object) -> dict:
    payload = {
        "resume_id": "resume-1",
        "interview_type": "experienced",
        "target_role": "backend",
        "language": "java",
        "target_level": "intermediate",
        "duration_minutes": 45,
        "focus_topics": ["项目深挖", "系统设计"],
        "jd_text": "",
    }
    payload.update(overrides)
    return payload


def test_template_fallback_plan_passes_validation() -> None:
    configuration = _base_configuration()
    resume = {
        "personal_info": "Java 后端",
        "highlights": [],
        "technical_skills": ["Java"],
        "work_experience": [],
        "project_experience": [{"name": "订单系统", "detail": "高并发改造"}],
        "resume_text": "参与订单系统项目",
    }
    raw = build_template_fallback_plan(configuration=configuration, resume=resume)
    candidate_summary = raw.pop("candidate_summary")
    result = validate_and_normalize_plan({**raw, "candidate_summary": candidate_summary}, configuration=configuration)
    assert len(result.plan["topics"]) == 5
    assert result.candidate_summary["focus_topics"] == configuration["focus_topics"]


def test_validation_rejects_too_few_topics() -> None:
    configuration = _base_configuration()
    with pytest.raises(PlanValidationError, match="主题数量"):
        validate_and_normalize_plan({"topics": [], "candidate_summary": {"focus_topics": ["项目深挖"], "reference_summary": ["a"]}}, configuration=configuration)


def test_validation_rejects_summary_leaking_opening_question() -> None:
    configuration = _base_configuration()
    resume = {
        "personal_info": "Java 后端",
        "highlights": [],
        "technical_skills": ["Java"],
        "work_experience": [],
        "project_experience": [{"name": "订单系统", "detail": "高并发改造"}],
        "resume_text": "参与订单系统项目",
    }
    raw = build_template_fallback_plan(configuration=configuration, resume=resume)
    opening = raw["topics"][0]["opening_question"]
    raw["candidate_summary"]["reference_summary"] = [opening]
    with pytest.raises(PlanValidationError, match="不得泄露"):
        validate_and_normalize_plan(raw, configuration=configuration)


def test_validation_normalizes_minutes_over_budget() -> None:
    configuration = _base_configuration()
    resume = {
        "personal_info": "Java 后端",
        "highlights": [],
        "technical_skills": ["Java"],
        "work_experience": [],
        "project_experience": [{"name": "订单系统", "detail": "高并发改造"}],
        "resume_text": "参与订单系统项目",
    }
    raw = build_template_fallback_plan(configuration=configuration, resume=resume)
    candidate_summary = raw.pop("candidate_summary")
    topics = list(raw["topics"])
    for topic in topics:
        topic["estimated_minutes"] = 9

    result = validate_and_normalize_plan(
        {**raw, "topics": topics, "candidate_summary": candidate_summary},
        configuration=configuration,
    )
    minutes = [topic["estimated_minutes"] for topic in result.plan["topics"]]
    assert len(minutes) == 5
    assert sum(minutes) == 40
    assert all(1 <= value <= 15 for value in minutes)


def test_validation_trims_six_topics_to_five() -> None:
    configuration = _base_configuration()
    resume = {
        "personal_info": "Java 后端",
        "highlights": [],
        "technical_skills": ["Java"],
        "work_experience": [],
        "project_experience": [{"name": "订单系统", "detail": "高并发改造"}],
        "resume_text": "参与订单系统项目",
    }
    raw = build_template_fallback_plan(configuration=configuration, resume=resume)
    candidate_summary = raw.pop("candidate_summary")
    topics = list(raw["topics"])
    topics.append(
        {
            **topics[-1],
            "id": "topic-6",
            "name": "补充方向",
            "required": False,
            "estimated_minutes": 5,
        }
    )

    result = validate_and_normalize_plan(
        {**raw, "topics": topics, "candidate_summary": candidate_summary},
        configuration=configuration,
    )
    assert len(result.plan["topics"]) == 5
    assert all(topic["name"] != "补充方向" for topic in result.plan["topics"])


def test_campus_and_experienced_templates_differ() -> None:
    resume = {"personal_info": "", "highlights": [], "technical_skills": [], "work_experience": [], "project_experience": []}
    experienced = build_template_fallback_plan(configuration=_base_configuration(), resume=resume)
    campus = build_template_fallback_plan(
        configuration=_base_configuration(interview_type="campus", focus_topics=["学习能力"]),
        resume=resume,
    )
    experienced_names = [topic["name"] for topic in experienced["topics"]]
    campus_names = [topic["name"] for topic in campus["topics"]]
    assert experienced_names != campus_names
    assert "项目所有权" in experienced_names
    assert "技术基础" in campus_names
