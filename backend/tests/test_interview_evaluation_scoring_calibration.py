from app.services.interview_evaluation.competencies import derive_competencies
from app.services.interview_evaluation.presentation import resolve_competency_status_label


def _backend_switch_plan() -> dict:
    return {
        "topics": [
            {
                "id": "topic-1",
                "name": "后端开发转型动机与技术储备",
                "dimension": "转型动机",
                "expected_signals": ["转型动机", "技术储备"],
                "evaluation_criteria": "是否说明转型原因与当前技术准备",
            }
        ]
    }


def test_negative_heavy_partial_scores_at_floor() -> None:
    """负面为主、无正向证据时不应再拿到 2 分（40 分）地板。"""
    plan_json = _backend_switch_plan()
    evaluation_context = {
        "evidence_by_topic": {
            "topic-1": {
                "evidence": [
                    {
                        "topic_id": "topic-1",
                        "matched_signal": "转型动机",
                        "polarity": "negative",
                        "quote": "后端好找工作",
                        "strength": 0.72,
                    },
                    {
                        "topic_id": "topic-1",
                        "matched_signal": "技术储备",
                        "polarity": "negative",
                        "quote": "还没有开始学习 python",
                        "strength": 0.78,
                    },
                ],
                "covered_signals": ["转型动机"],
                "missing_signals": ["技术储备"],
            }
        },
        "risks": [],
        "unverified_items": [],
    }
    competencies = derive_competencies(
        plan_json=plan_json,
        evaluation_context=evaluation_context,
        runtime_state={"completed_topic_ids": ["topic-1"]},
    )
    assert len(competencies) == 1
    assert competencies[0]["status"] == "partially_verified"
    assert competencies[0]["score"] == 1
    assert resolve_competency_status_label("partially_verified", 1) == "明显不足，未达基本要求"


def test_partial_with_positive_evidence_scores_higher_than_negative_only() -> None:
    plan_json = _backend_switch_plan()
    evaluation_context = {
        "evidence_by_topic": {
            "topic-1": {
                "evidence": [
                    {
                        "topic_id": "topic-1",
                        "matched_signal": "转型动机",
                        "polarity": "positive",
                        "quote": "希望深入理解服务端架构",
                        "strength": 0.75,
                    },
                    {
                        "topic_id": "topic-1",
                        "matched_signal": "技术储备",
                        "polarity": "negative",
                        "quote": "Python 项目经验还不多",
                        "strength": 0.6,
                    },
                ],
                "covered_signals": ["转型动机"],
                "missing_signals": ["技术储备"],
            }
        },
        "risks": [],
        "unverified_items": [],
    }
    competencies = derive_competencies(
        plan_json=plan_json,
        evaluation_context=evaluation_context,
        runtime_state={"completed_topic_ids": ["topic-1"]},
    )
    assert competencies[0]["score"] is not None
    assert competencies[0]["score"] >= 2


def test_resolve_competency_status_label_by_score() -> None:
    assert resolve_competency_status_label("partially_verified", 1) == "明显不足，未达基本要求"
    assert resolve_competency_status_label("partially_verified", 2) == "明显不足，未达基本要求"
    assert resolve_competency_status_label("partially_verified", 3) == "基本到位，仍有明显缺口"
    assert resolve_competency_status_label("partially_verified", 4) == "有亮点，仍需加强"
