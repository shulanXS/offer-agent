import pytest

from app.core.errors import ErrorCode
from app.services.interview_planning.request_validation import validate_regeneration_request


def test_validate_regeneration_request_accepts_valid_payload() -> None:
    result = validate_regeneration_request(
        {
            "regeneration_strategy": "align_resume",
            "additional_instruction": "",
        },
        configuration={
            "focus_topics": ["项目深挖", "系统设计"],
            "jd_text": "",
        },
    )
    assert result["regeneration_strategy"] == "align_resume"
    assert result["additional_instruction"] == ""


def test_validate_regeneration_request_accepts_different_plan_with_instruction() -> None:
    result = validate_regeneration_request(
        {
            "regeneration_strategy": "different_plan",
            "additional_instruction": "希望更偏分布式经验",
        },
        configuration={"focus_topics": ["项目深挖"], "jd_text": ""},
    )
    assert result["regeneration_strategy"] == "different_plan"
    assert result["additional_instruction"] == "希望更偏分布式经验"


def test_validate_regeneration_request_rejects_instruction_for_other_strategies() -> None:
    with pytest.raises(Exception) as exc:
        validate_regeneration_request(
            {
                "regeneration_strategy": "align_resume",
                "additional_instruction": "希望更多项目细节",
            },
            configuration={"focus_topics": [], "jd_text": ""},
        )
    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == ErrorCode.INTERVIEW_CONFIG_INVALID.value


def test_validate_regeneration_request_rejects_unknown_strategy() -> None:
    with pytest.raises(Exception) as exc:
        validate_regeneration_request(
            {"regeneration_strategy": "adjust_topics", "additional_instruction": ""},
            configuration={"focus_topics": [], "jd_text": ""},
        )
    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == ErrorCode.INTERVIEW_CONFIG_INVALID.value
