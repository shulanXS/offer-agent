from app.agent.interview_planning.prompts import _build_regeneration_block, build_planning_prompt
from app.services.interview_planning.regeneration import build_previous_plan_summary


def _sample_plan_record() -> dict:
    return {
        "version": 1,
        "plan_json": {
            "topics": [
                {
                    "name": "项目所有权",
                    "dimension": "项目经历真实性验证",
                    "required": True,
                    "estimated_minutes": 8,
                    "focus_points": ["核心项目", "个人职责"],
                },
                {
                    "name": "技术深度",
                    "dimension": "技术深度",
                    "required": True,
                    "estimated_minutes": 8,
                    "focus_points": ["实现细节"],
                },
            ]
        },
        "candidate_summary_json": {
            "focus_topics": ["项目深挖", "系统设计"],
            "reference_summary": ["将重点参考订单系统项目"],
        },
    }


def test_build_previous_plan_summary_includes_topic_details() -> None:
    summary = build_previous_plan_summary(_sample_plan_record())

    assert summary["topics"][0]["dimension"] == "项目经历真实性验证"
    assert summary["topics"][0]["focus_points"] == ["核心项目", "个人职责"]


def test_regeneration_block_includes_strategy_instructions() -> None:
    block = _build_regeneration_block(
        previous_plan_summary=build_previous_plan_summary(_sample_plan_record()),
        regeneration_feedback={
            "regeneration_strategy": "align_jd",
            "additional_instruction": "",
        },
    )

    assert "本策略必须遵守" in block
    assert "jd:" in block
    assert "dimension=项目经历真实性验证" in block


def test_different_plan_includes_additional_instruction_in_prompt() -> None:
    configuration = {
        "interview_type": "experienced",
        "target_role": "backend",
        "language": "java",
        "target_level": "intermediate",
        "focus_topics": ["项目深挖", "系统设计"],
        "jd_text": "",
        "interview_language": "zh",  # v1.1
    }
    resume = {
        "personal_info": "",
        "highlights": [],
        "technical_skills": [],
        "work_experience": [],
        "project_experience": [],
    }
    prompt, _ = build_planning_prompt(
        configuration=configuration,
        resume=resume,
        regeneration_feedback={
            "regeneration_strategy": "different_plan",
            "additional_instruction": "希望更偏分布式",
        },
        previous_plan_summary=build_previous_plan_summary(_sample_plan_record()),
    )

    assert "用户补充说明（换套首要意图）: 希望更偏分布式" in prompt


def test_non_different_plan_omits_additional_instruction_in_block() -> None:
    block = _build_regeneration_block(
        previous_plan_summary=build_previous_plan_summary(_sample_plan_record()),
        regeneration_feedback={
            "regeneration_strategy": "align_resume",
            "additional_instruction": "这段不应出现",
        },
    )

    assert "这段不应出现" not in block
