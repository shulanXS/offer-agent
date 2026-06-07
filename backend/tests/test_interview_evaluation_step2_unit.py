from app.services.interview_evaluation.competencies import derive_competencies
from app.services.interview_evaluation.minimal_report import build_minimal_evaluation_report
from app.services.interview_evaluation.report import build_evidence_driven_report, validate_competencies


def _sample_plan() -> dict:
    return {
        "topics": [
            {
                "id": "topic-1",
                "name": "项目深挖",
                "dimension": "项目经历",
                "expected_signals": ["个人贡献", "结果指标"],
                "evaluation_criteria": "是否能说明个人贡献与结果",
            },
            {
                "id": "topic-2",
                "name": "系统设计",
                "dimension": "方案取舍",
                "expected_signals": ["备选方案"],
                "evaluation_criteria": "是否能说明方案取舍",
            },
        ]
    }


def test_derive_competencies_verified_with_full_signal_coverage() -> None:
    plan_json = _sample_plan()
    evaluation_context = {
        "evidence_by_topic": {
            "topic-1": {
                "evidence": [
                    {
                        "topic_id": "topic-1",
                        "matched_signal": "个人贡献",
                        "polarity": "positive",
                        "quote": "我负责核心模块设计",
                        "strength": 0.85,
                    },
                    {
                        "topic_id": "topic-1",
                        "matched_signal": "结果指标",
                        "polarity": "positive",
                        "quote": "QPS 提升 30%",
                        "strength": 0.8,
                    },
                ],
                "covered_signals": ["个人贡献", "结果指标"],
                "missing_signals": [],
            },
            "topic-2": {
                "evidence": [],
                "covered_signals": [],
                "missing_signals": ["备选方案"],
            },
        },
        "risks": [],
        "unverified_items": [],
    }
    competencies = derive_competencies(
        plan_json=plan_json,
        evaluation_context=evaluation_context,
        runtime_state={"completed_topic_ids": ["topic-1"]},
    )
    assert len(competencies) == 2
    assert competencies[0]["status"] == "verified"
    assert competencies[0]["score"] is not None
    assert 1 <= competencies[0]["score"] <= 5
    assert competencies[0]["evidence_references"]
    assert competencies[1]["status"] == "unverified"
    assert competencies[1]["score"] is None


def test_unverified_competency_has_no_score() -> None:
    plan_json = _sample_plan()
    competencies = derive_competencies(
        plan_json=plan_json,
        evaluation_context={"evidence_by_topic": {}, "risks": [], "unverified_items": []},
        runtime_state={"completed_topic_ids": []},
    )
    for item in competencies:
        if item["status"] == "unverified":
            assert item["score"] is None


def test_build_evidence_driven_report_without_agent() -> None:
    plan_json = _sample_plan()
    evaluation_context = {
        "configuration": {"interview_type": "experienced"},
        "confirmed_plan": plan_json,
        "evidence_by_topic": {
            "topic-1": {
                "evidence": [
                    {
                        "topic_id": "topic-1",
                        "matched_signal": "个人贡献",
                        "polarity": "positive",
                        "quote": "我负责核心模块设计",
                        "strength": 0.85,
                    }
                ],
                "covered_signals": ["个人贡献"],
                "missing_signals": ["结果指标"],
            },
            "topic-2": {"evidence": [], "covered_signals": [], "missing_signals": ["备选方案"]},
        },
        "risks": ["项目规模描述前后不一致"],
        "unverified_items": [{"topic_id": "topic-2", "content": "尚未验证的系统设计能力"}],
    }
    report = build_evidence_driven_report(
        plan_json=plan_json,
        configuration={"interview_type": "experienced"},
        runtime_state={"completed_topic_ids": ["topic-1"]},
        evaluation_context=evaluation_context,
        use_agent=False,
    )
    assert report["source"] == "evidence_rule"
    assert len(report["competencies"]) == 2
    assert report["overall_score"] is not None
    validate_competencies(report["competencies"], plan_json=plan_json)
    assert report["jd_match"] is None
    assert len(report["question_reviews"]) == 2
    assert report["practice_recommendations"]
    assert report["candidate_review"]["summary"]
    assert report["competencies"][0]["evaluation_comment"]


def test_minimal_report_still_available_as_fallback_shape() -> None:
    report = build_minimal_evaluation_report(
        plan_json=_sample_plan(),
        configuration={"interview_type": "experienced"},
        runtime_state={"completed_topic_ids": ["topic-1"]},
        evaluation_context={
            "evidence_by_topic": {},
            "risks": [],
            "unverified_items": [],
        },
    )
    assert report["source"] == "rule_minimal"
    assert report["competencies"] == []
    assert report["overall_score"] is None
    assert report["candidate_review"]["headline"]
