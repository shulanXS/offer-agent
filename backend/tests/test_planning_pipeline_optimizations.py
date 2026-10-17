import pytest

from app.agent.interview_planning.agent import (
    categorize_validation_failure,
    record_planning_outcome,
    record_validation_failure,
    reset_snapshot_for_tests,
    snapshot,
)
from app.agent.interview_planning.templates import build_template_fallback_plan
from app.agent.interview_planning.validator import PlanValidationError, assert_required_dimensions, validate_and_normalize_plan
from app.services.interview_planning.preview import build_plan_preview
from app.services.interview_planning.regeneration import plans_have_effective_difference, validate_regeneration_strategy_outcome


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


def _resume(**overrides: object) -> dict:
    payload = {
        "personal_info": "Java 后端",
        "highlights": [],
        "technical_skills": ["Java"],
        "work_experience": [],
        "project_experience": [{"name": "订单系统", "detail": "高并发改造"}],
        "resume_text": "参与订单系统项目",
    }
    payload.update(overrides)
    return payload


def _validated_plan(**configuration_overrides: object) -> tuple[dict, dict]:
    configuration = _base_configuration(**configuration_overrides)
    raw = build_template_fallback_plan(configuration=configuration, resume=_resume())
    candidate_summary = raw.pop("candidate_summary")
    result = validate_and_normalize_plan({**raw, "candidate_summary": candidate_summary}, configuration=configuration)
    return result.plan, result.candidate_summary


def test_dimension_alias_accepts_architecture_design_label() -> None:
    plan, _ = _validated_plan()
    topics = [{**plan["topics"][2], "dimension": "架构设计", "name": "方案取舍"}]
    assert_required_dimensions(topics + plan["topics"][:2] + plan["topics"][3:], interview_type="experienced")


def test_dimension_alias_rejects_missing_bucket() -> None:
    plan, _ = _validated_plan()
    topics = [{**topic, "name": "通用沟通", "dimension": "软技能", "focus_points": ["表达"]} for topic in plan["topics"]]
    with pytest.raises(PlanValidationError, match="必须维度未覆盖"):
        assert_required_dimensions(topics, interview_type="experienced")


@pytest.mark.parametrize(('interview_type', 'dimensions'), [
    ('experienced', ['Project Ownership', 'Technical Depth', 'System Design', 'Engineering Quality']),
    ('campus', ['Technical Fundamentals', 'Internship Experience', 'Problem Analysis', 'Learning Potential']),
])
def test_english_dimensions_preserve_required_coverage(interview_type, dimensions) -> None:
    topics = [{'name': dimension, 'dimension': dimension, 'focus_points': []} for dimension in dimensions]
    assert_required_dimensions(topics, interview_type=interview_type)
    with pytest.raises(PlanValidationError, match='必须维度未覆盖'):
        assert_required_dimensions(topics[:-1], interview_type=interview_type)


def test_deeper_diff_detects_focus_points_change() -> None:
    previous = {
        "plan_json": {
            "topics": [
                {
                    "name": "项目所有权",
                    "dimension": "项目经历",
                    "focus_points": ["核心项目"],
                    "opening_question": "请介绍你在订单系统中的职责",
                }
            ]
        },
        "candidate_summary_json": {"reference_summary": ["a"], "focus_topics": ["项目深挖"]},
    }
    current = {
        "plan_json": {
            "topics": [
                {
                    "name": "项目所有权",
                    "dimension": "项目经历",
                    "focus_points": ["核心项目", "个人贡献"],
                    "opening_question": "请介绍你在订单系统中的职责",
                }
            ]
        },
        "candidate_summary_json": {"reference_summary": ["a"], "focus_topics": ["项目深挖"]},
    }
    assert plans_have_effective_difference(previous, current)


def test_strategy_validation_align_jd() -> None:
    plan, candidate_summary = _validated_plan(jd_text="负责 Java 微服务开发，熟悉 Spring Cloud")
    candidate_summary = {**candidate_summary, "reference_summary": ["岗位重点：Java 微服务开发"]}
    validate_regeneration_strategy_outcome(
        plan=plan,
        candidate_summary=candidate_summary,
        configuration=_base_configuration(jd_text="负责 Java 微服务开发，熟悉 Spring Cloud"),
        resume=_resume(),
        regeneration_feedback={"regeneration_strategy": "align_jd"},
        previous_plan_summary=None,
    )


def test_strategy_validation_different_plan() -> None:
    plan, candidate_summary = _validated_plan()
    previous_topics = [{"name": topic["name"], "dimension": topic["dimension"]} for topic in plan["topics"]]
    topics = [dict(topic) for topic in plan["topics"]]
    for index, topic in enumerate(topics):
        topic["name"] = f"新主题{index + 1}"
        topic["dimension"] = f"新维度{index + 1}"
    validate_regeneration_strategy_outcome(
        plan={"topics": topics},
        candidate_summary=candidate_summary,
        configuration=_base_configuration(),
        resume=_resume(),
        regeneration_feedback={"regeneration_strategy": "different_plan"},
        previous_plan_summary={"topics": previous_topics},
    )


def test_preview_exposes_generation_meta() -> None:
    preview = build_plan_preview(
        session_id="session-1",
        plan_record={
            "id": "plan-1",
            "version": 1,
            "plan_json": {
                "topics": [],
                "generation_meta": {
                    "source": "llm",
                    "generation_attempts": 2,
                    "degraded": False,
                },
            },
            "candidate_summary_json": {"focus_topics": ["项目深挖"], "reference_summary": ["a"]},
        },
        configuration=_base_configuration(),
        status="plan_ready",
    )
    assert preview["generation_meta"] == {
        "source": "llm",
        "generation_attempts": 2,
        "degraded": False,
        "degraded_reason": None,
    }


def test_telemetry_snapshot_tracks_failures_and_outcomes() -> None:
    reset_snapshot_for_tests()
    record_validation_failure("社招必须维度未覆盖: 技术深度", trace_id="t1")
    record_planning_outcome(source="llm", degraded=False, attempts=1, trace_id="t1")
    record_planning_outcome(source="template_fallback", degraded=True, attempts=3, trace_id="t2")

    data = snapshot()
    assert data["validation_failures"]["dimension_coverage"] == 1
    assert data["outcomes"]["source=llm|degraded=False|attempts=1"] == 1
    assert categorize_validation_failure("align_jd 策略要求") == "regeneration_strategy"
