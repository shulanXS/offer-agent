from app.services.interview_evaluation.practice_recommendations import build_practice_recommendations, map_topic_to_focus_topic
from app.services.interview_evaluation.question_reviews import build_question_reviews, validate_question_reviews


def _sample_plan() -> dict:
    return {
        "topics": [
            {
                "id": "topic-1",
                "name": "项目深挖",
                "dimension": "项目经历",
                "objective": "验证候选人在项目中的个人贡献",
                "expected_signals": ["个人贡献", "结果指标"],
                "evaluation_criteria": "是否能说明个人贡献与结果",
            },
            {
                "id": "topic-2",
                "name": "系统设计",
                "dimension": "方案取舍",
                "objective": "考察方案设计与取舍能力",
                "expected_signals": ["备选方案"],
                "evaluation_criteria": "是否能说明方案取舍",
            },
        ]
    }


def _competencies() -> list[dict]:
    return [
        {
            "topic_id": "topic-1",
            "name": "项目深挖",
            "dimension": "项目经历",
            "status": "verified",
            "score": 4,
            "confidence": 0.82,
            "strengths": ["个人贡献 — 我负责核心模块"],
            "risks": [],
            "evidence_references": [{"quote": "我负责核心模块", "matched_signal": "个人贡献", "polarity": "positive", "strength": 0.8}],
        },
        {
            "topic_id": "topic-2",
            "name": "系统设计",
            "dimension": "方案取舍",
            "status": "unverified",
            "score": None,
            "confidence": 0.25,
            "strengths": [],
            "risks": [],
            "evidence_references": [],
        },
    ]


def test_build_question_reviews_aligns_with_plan() -> None:
    plan_json = _sample_plan()
    evaluation_context = {
        "evidence_by_topic": {
            "topic-1": {
                "evidence": [
                    {
                        "topic_id": "topic-1",
                        "matched_signal": "个人贡献",
                        "polarity": "positive",
                        "quote": "我负责核心模块",
                        "strength": 0.8,
                    }
                ],
                "covered_signals": ["个人贡献"],
                "missing_signals": ["结果指标"],
            },
            "topic-2": {"evidence": [], "covered_signals": [], "missing_signals": ["备选方案"]},
        },
        "messages_by_topic": {
            "topic-1": [{"role": "user", "content": "我负责核心模块开发"}],
            "topic-2": [],
        },
    }
    reviews = build_question_reviews(
        plan_json=plan_json,
        evaluation_context=evaluation_context,
        competencies=_competencies(),
        runtime_state={"completed_topic_ids": ["topic-1"]},
    )
    validate_question_reviews(reviews, plan_json=plan_json)
    assert reviews[0]["objective"]
    assert reviews[0]["effective_points"]
    assert reviews[0]["organization_tips"]
    assert reviews[0]["evidence_quotes"]
    assert reviews[1]["gaps_and_risks"]


def test_build_practice_recommendations_for_weak_topics() -> None:
    plan_json = _sample_plan()
    competencies = [
        {
            "topic_id": "topic-1",
            "name": "项目深挖",
            "dimension": "项目经历",
            "status": "partially_verified",
            "score": 2,
            "confidence": 0.55,
            "strengths": [],
            "risks": ["结果指标 — 缺少量化结果"],
            "evidence_references": [],
        },
        {
            "topic_id": "topic-2",
            "name": "系统设计",
            "dimension": "方案取舍",
            "status": "partially_verified",
            "score": 2,
            "confidence": 0.5,
            "strengths": [],
            "risks": ["备选方案 — 未说明取舍"],
            "evidence_references": [],
        },
    ]
    reviews = build_question_reviews(
        plan_json=plan_json,
        evaluation_context={
            "evidence_by_topic": {
                "topic-1": {
                    "evidence": [{"quote": "负责模块", "polarity": "positive", "strength": 0.6}],
                    "covered_signals": ["个人贡献"],
                    "missing_signals": ["结果指标"],
                },
                "topic-2": {
                    "evidence": [{"quote": "微服务拆分", "polarity": "positive", "strength": 0.55}],
                    "covered_signals": [],
                    "missing_signals": ["备选方案"],
                },
            },
            "messages_by_topic": {
                "topic-1": [{"role": "user", "content": "负责模块"}],
                "topic-2": [{"role": "user", "content": "微服务拆分"}],
            },
        },
        competencies=competencies,
        runtime_state={"completed_topic_ids": ["topic-1", "topic-2"]},
    )
    recommendations = build_practice_recommendations(
        plan_json=plan_json,
        competencies=competencies,
        question_reviews=reviews,
    )
    assert recommendations
    assert len(recommendations) <= 5
    assert all(item["focus_topic"] for item in recommendations)
    assert all(item["summary"] for item in recommendations)
    assert all(item["priority"] in {"high", "medium"} for item in recommendations)
    focus_topics = [item["focus_topic"] for item in recommendations]
    assert len(focus_topics) == len(set(focus_topics))


def test_build_practice_recommendations_skip_unverified_topics() -> None:
    plan_json = _sample_plan()
    competencies = _competencies()
    reviews = build_question_reviews(
        plan_json=plan_json,
        evaluation_context={
            "evidence_by_topic": {
                "topic-1": {"evidence": [], "covered_signals": ["个人贡献"], "missing_signals": []},
                "topic-2": {"evidence": [], "covered_signals": [], "missing_signals": ["备选方案"]},
            },
            "messages_by_topic": {"topic-1": [], "topic-2": []},
        },
        competencies=competencies,
        runtime_state={"completed_topic_ids": ["topic-1"]},
    )
    recommendations = build_practice_recommendations(
        plan_json=plan_json,
        competencies=competencies,
        question_reviews=reviews,
    )
    assert recommendations == []


def test_build_practice_recommendations_merge_same_focus_topic() -> None:
    plan_json = {
        "topics": [
            {
                "id": "topic-1",
                "name": "核心项目贡献",
                "dimension": "项目经历",
                "expected_signals": ["个人贡献"],
            },
            {
                "id": "topic-2",
                "name": "技术转型路径",
                "dimension": "项目经历",
                "expected_signals": ["成长路径"],
            },
        ]
    }
    competencies = [
        {
            "topic_id": "topic-1",
            "name": "核心项目贡献",
            "dimension": "项目经历",
            "status": "partially_verified",
            "score": 2,
            "risks": ["缺少结果指标"],
        },
        {
            "topic_id": "topic-2",
            "name": "技术转型路径",
            "dimension": "项目经历",
            "status": "partially_verified",
            "score": 2,
            "risks": ["成长路径不清晰"],
        },
    ]
    reviews = build_question_reviews(
        plan_json=plan_json,
        evaluation_context={
            "evidence_by_topic": {
                "topic-1": {
                    "evidence": [{"quote": "项目A", "polarity": "positive", "strength": 0.6}],
                    "covered_signals": [],
                    "missing_signals": ["个人贡献"],
                },
                "topic-2": {
                    "evidence": [{"quote": "转型经历", "polarity": "positive", "strength": 0.55}],
                    "covered_signals": [],
                    "missing_signals": ["成长路径"],
                },
            },
            "messages_by_topic": {
                "topic-1": [{"role": "user", "content": "项目A"}],
                "topic-2": [{"role": "user", "content": "转型经历"}],
            },
        },
        competencies=competencies,
        runtime_state={"completed_topic_ids": ["topic-1", "topic-2"]},
    )
    recommendations = build_practice_recommendations(
        plan_json=plan_json,
        competencies=competencies,
        question_reviews=reviews,
    )
    assert len(recommendations) == 1
    assert recommendations[0]["focus_topic"] == "项目深挖"
    assert recommendations[0]["title"] == "加强「项目深挖」"
    assert recommendations[0]["summary"]
    assert "建议" in recommendations[0]["summary"]


def test_map_topic_to_focus_topic() -> None:
    assert map_topic_to_focus_topic(topic_name="Java 微服务架构", dimension="后端开发") == "系统设计"
    assert map_topic_to_focus_topic(topic_name="项目深挖", dimension="项目经历") == "项目深挖"
