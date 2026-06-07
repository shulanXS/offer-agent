from app.services.interview_evaluation.candidate_report import build_candidate_review, enrich_competencies_for_candidate
from app.services.interview_evaluation.minimal_report import build_minimal_evaluation_report
from app.services.interview_evaluation.report import build_evidence_driven_report, _merge_candidate_review


def _sample_plan() -> dict:
    return {
        "topics": [
            {
                "id": "topic-1",
                "name": "项目深挖",
                "dimension": "项目经历",
                "expected_signals": ["个人贡献"],
                "evaluation_criteria": "是否能说明个人贡献与结果",
            }
        ]
    }


def test_build_candidate_review_uses_plain_language() -> None:
    review = build_candidate_review(
        competencies=[
            {
                "topic_id": "topic-1",
                "name": "项目深挖",
                "status": "partially_verified",
                "score": 3,
                "risks": ["缺少量化结果"],
            }
        ],
        question_reviews=[
            {
                "topic_id": "topic-1",
                "organization_tips": ["先讲结论，再补充背景与结果"],
            }
        ],
        practice_recommendations=[
            {
                "title": "项目表达",
                "focus_topic": "项目深挖",
                "suggested_actions": ["准备 2 分钟 STAR 回答"],
            }
        ],
        overall_score=62,
        risks=["回答前后细节不一致"],
        unverified_items=[],
        configuration={"interview_type": "experienced"},
    )
    assert review["headline"]
    assert "模拟面试" in review["summary"]
    assert review["weaknesses"]
    assert review["suggestions"]


def test_build_candidate_review_partial_coverage_copy() -> None:
    review = build_candidate_review(
        competencies=[
            {
                "topic_id": "topic-1",
                "name": "Redis 基础",
                "status": "partially_verified",
                "score": 2,
                "risks": ["持久化细节缺失"],
            },
            {
                "topic_id": "topic-2",
                "name": "项目深挖",
                "status": "unverified",
                "score": None,
                "risks": [],
            },
        ],
        question_reviews=[],
        practice_recommendations=[],
        overall_score=40,
        risks=[],
        unverified_items=[],
        configuration={"interview_type": "experienced"},
        completed_topic_count=1,
        total_topic_count=6,
        scored_topic_count=1,
    )
    assert "已讨论的考察点" in review["headline"]
    assert "已评分的 1 个考察点" in review["summary"]
    assert "未计入综合分" in review["summary"]
    assert review["overall_score_label"] == "已评考察点均分"
    assert "综合分仅反映已评分内容" in review["coverage_note"]
    assert not any("讨论不足" in item["body"] for item in review["weaknesses"])


def test_build_candidate_review_strong_performance_allows_empty_feedback() -> None:
    review = build_candidate_review(
        competencies=[
            {
                "topic_id": "topic-1",
                "name": "Redis 基础",
                "status": "verified",
                "score": 5,
                "risks": [],
                "evidence_references": [
                    {
                        "quote": "Redis 单线程通过 IO 多路复用处理并发",
                        "matched_signal": "并发模型",
                        "polarity": "positive",
                        "strength": 0.9,
                    }
                ],
            }
        ],
        question_reviews=[],
        practice_recommendations=[],
        overall_score=100,
        risks=[],
        unverified_items=[],
        configuration={"interview_type": "experienced"},
        completed_topic_count=1,
        total_topic_count=1,
        scored_topic_count=1,
    )
    assert review["highlights"]
    assert review["weaknesses"] == []
    assert review["suggestions"] == []
    assert "主要问题" not in review["summary"]


def test_build_candidate_review_includes_measured_highlights() -> None:
    review = build_candidate_review(
        competencies=[
            {
                "topic_id": "topic-1",
                "name": "Redis 基础",
                "status": "verified",
                "score": 4,
                "strengths": [],
                "evidence_references": [
                    {
                        "quote": "Redis 单线程通过 IO 多路复用处理并发",
                        "matched_signal": "并发模型",
                        "polarity": "positive",
                        "strength": 0.85,
                    }
                ],
            }
        ],
        question_reviews=[],
        practice_recommendations=[],
        overall_score=80,
        risks=[],
        unverified_items=[],
        configuration={"interview_type": "experienced"},
        total_topic_count=1,
        scored_topic_count=1,
    )
    assert review["highlights"]
    assert review["highlights"][0]["title"] == "Redis 基础"
    assert "比较清楚" in review["highlights"][0]["body"]


def test_enrich_competencies_adds_evaluation_comment() -> None:
    enriched = enrich_competencies_for_candidate(
        [
            {
                "topic_id": "topic-1",
                "name": "项目深挖",
                "status": "verified",
                "score": 4,
                "strengths": ["我负责核心模块设计"],
                "risks": [],
                "evidence_references": [],
            }
        ],
        question_reviews=[],
        agent_comments={},
    )
    assert enriched[0]["evaluation_comment"]
    assert "项目深挖" in enriched[0]["evaluation_comment"]


def test_merge_candidate_review_prefers_agent_text() -> None:
    merged = _merge_candidate_review(
        {
            "headline": "规则标题",
            "summary": "规则摘要",
            "highlights": [{"title": "规则亮点", "body": "规则亮点正文"}],
            "weaknesses": [{"title": "规则不足", "body": "规则不足正文"}],
            "suggestions": [{"title": "规则建议", "body": "规则建议正文"}],
        },
        {
            "headline": "Agent 标题",
            "summary": "Agent 摘要",
            "highlights": [{"title": "Agent 亮点", "body": "Agent 亮点正文"}],
            "weaknesses": [{"title": "Agent 不足", "body": "Agent 不足正文"}],
            "suggestions": [{"title": "Agent 建议", "body": "Agent 建议正文"}],
        },
    )
    assert merged["headline"] == "Agent 标题"
    assert merged["summary"] == "Agent 摘要"
    assert merged["highlights"] == [{"title": "Agent 亮点", "body": "Agent 亮点正文"}]
    assert merged["weaknesses"] == [{"title": "Agent 不足", "body": "Agent 不足正文"}]


def test_merge_candidate_review_allows_agent_empty_lists() -> None:
    merged = _merge_candidate_review(
        {
            "headline": "规则标题",
            "summary": "规则摘要",
            "highlights": [{"title": "规则亮点", "body": "规则亮点正文"}],
            "weaknesses": [{"title": "规则不足", "body": "规则不足正文"}],
            "suggestions": [{"title": "规则建议", "body": "规则建议正文"}],
        },
        {
            "headline": "Agent 标题",
            "summary": "Agent 摘要",
            "highlights": [{"title": "Agent 亮点", "body": "Agent 亮点正文"}],
            "weaknesses": [],
            "suggestions": [],
        },
    )
    assert merged["weaknesses"] == []
    assert merged["suggestions"] == []


def test_evidence_driven_report_includes_candidate_review() -> None:
    plan_json = _sample_plan()
    report = build_evidence_driven_report(
        plan_json=plan_json,
        configuration={"interview_type": "experienced"},
        runtime_state={"completed_topic_ids": ["topic-1"]},
        evaluation_context={
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
                    "missing_signals": [],
                }
            },
            "risks": [],
            "unverified_items": [],
        },
        use_agent=False,
    )
    assert report["candidate_review"]["summary"]
    assert report["summary"] == report["candidate_review"]["summary"]
    assert report["competencies"][0]["evaluation_comment"]
    assert report["coverage"]["scored_topic_count"] == 1
    assert report["candidate_review"]["coverage_note"]


def test_minimal_report_includes_candidate_review() -> None:
    report = build_minimal_evaluation_report(
        plan_json=_sample_plan(),
        configuration={"interview_type": "experienced"},
        runtime_state={"completed_topic_ids": []},
        evaluation_context={"evidence_by_topic": {}, "risks": [], "unverified_items": []},
    )
    assert report["candidate_review"]["headline"]
    assert report["summary"]
