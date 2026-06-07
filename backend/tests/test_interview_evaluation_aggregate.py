from app.services.interview_evaluation.aggregate import count_discussed_topics
from app.services.interview_evaluation.candidate_report import build_score_coverage_context


def test_count_discussed_topics_uses_scored_when_completed_is_zero() -> None:
    competencies = [
        {"topic_id": "topic-1", "status": "verified", "score": 3},
        {"topic_id": "topic-2", "status": "unverified", "score": None},
    ]
    assert count_discussed_topics(competencies, completed_topic_count=0, scored_topic_count=1) == 1


def test_count_discussed_topics_ignores_completed_without_evidence() -> None:
    competencies = [
        {"topic_id": "topic-1", "status": "partially_verified", "score": 2},
        {"topic_id": "topic-2", "status": "partially_verified", "score": 2},
        {"topic_id": "topic-3", "status": "unverified", "score": None},
        {"topic_id": "topic-4", "status": "unverified", "score": None},
        {"topic_id": "topic-5", "status": "unverified", "score": None},
    ]
    assert count_discussed_topics(competencies, completed_topic_count=3, scored_topic_count=2) == 2


def test_build_score_coverage_context_shows_discussed_not_zero_when_scored() -> None:
    context = build_score_coverage_context(
        scored_topic_count=1,
        total_topic_count=5,
        completed_topic_count=0,
        discussed_topic_count=1,
    )
    assert "你聊到 1 个" in context["coverage_note"]
    assert "其中 1 个已有评分" in context["coverage_note"]
