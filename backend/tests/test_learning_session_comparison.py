from app.services.learning.aggregate import build_outcome_snapshot
from app.services.learning.session_comparison import build_session_comparison


def _outcome(
    *,
    session_id: str,
    completed_at: str,
    discussed: int,
    scored: int,
    total: int,
    signal_coverage_rate: float,
    overall_score: int | None,
    user_answer_rounds: int = 0,
) -> dict:
    competencies = []
    topics_evidence = {}
    for index in range(total):
        topic_id = f"topic-{index + 1}"
        is_discussed = index < discussed
        has_score = index < scored
        status = "partially_verified" if is_discussed else "unverified"
        competencies.append(
            {
                "topic_id": topic_id,
                "name": f"主题{index + 1}",
                "dimension": "项目经历",
                "status": status,
                "score": 2 if has_score else None,
                "answer_rounds": [{"question": "Q", "answer": "A"}] if is_discussed else [],
            }
        )
        if is_discussed:
            covered_count = max(1, int(signal_coverage_rate * 2))
            missing_count = max(0, 2 - covered_count)
            topics_evidence[topic_id] = {
                "missing_signals": [f"missing-{i}" for i in range(missing_count)],
                "covered_signals": [f"covered-{i}" for i in range(covered_count)],
                "evidence": [{"quote": "回答", "polarity": "positive"}],
            }
        else:
            topics_evidence[topic_id] = {
                "missing_signals": ["未聊"],
                "covered_signals": [],
                "evidence": [],
            }

    plan_json = {
        "topics": [
            {"id": f"topic-{index + 1}", "name": f"主题{index + 1}", "dimension": "项目经历"}
            for index in range(total)
        ]
    }
    return build_outcome_snapshot(
        session_id=session_id,
        completed_at=completed_at,
        plan_json=plan_json,
        evaluation={
            "overall_score": overall_score,
            "competencies": competencies,
            "coverage": {
                "total_topic_count": total,
                "discussed_topic_count": discussed,
                "scored_topic_count": scored,
            },
        },
        evidence_by_topic=topics_evidence,
    )


def test_build_session_comparison_returns_coverage_and_three_points() -> None:
    previous = {
        "session_id": "s1",
        "completed_at": "2026-06-01",
        "session_summary": {
            "discussed_topics": 3,
            "scored_topics": 2,
            "signal_coverage_rate": 0.45,
            "overall_score": 30,
            "user_answer_rounds": 6,
        },
    }
    current = {
        "session_id": "s2",
        "completed_at": "2026-06-02",
        "session_summary": {
            "discussed_topics": 2,
            "scored_topics": 2,
            "signal_coverage_rate": 0.62,
            "overall_score": 30,
            "user_answer_rounds": 4,
        },
    }

    comparison = build_session_comparison(current_outcome=current, previous_outcome=previous)
    assert comparison is not None
    assert comparison["discussed_coverage"]["baseline_count"] == 3
    assert comparison["discussed_coverage"]["current_count"] == 2
    assert len(comparison["points"]) == 3
    categories = {point["category"] for point in comparison["points"]}
    assert categories == {"depth", "performance", "engagement"}


def test_build_session_comparison_always_returns_three_points_when_flat() -> None:
    previous = _outcome(
        session_id="s1",
        completed_at="2026-06-01",
        discussed=2,
        scored=2,
        total=5,
        signal_coverage_rate=0.5,
        overall_score=30,
        user_answer_rounds=4,
    )
    current = _outcome(
        session_id="s2",
        completed_at="2026-06-02",
        discussed=2,
        scored=2,
        total=5,
        signal_coverage_rate=0.5,
        overall_score=30,
        user_answer_rounds=4,
    )

    comparison = build_session_comparison(current_outcome=current, previous_outcome=previous)
    assert comparison is not None
    assert len(comparison["points"]) == 3
    assert all(point["headline"] for point in comparison["points"])


def test_outcome_snapshot_includes_session_summary() -> None:
    outcome = _outcome(
        session_id="s1",
        completed_at="2026-06-01",
        discussed=2,
        scored=2,
        total=5,
        signal_coverage_rate=0.5,
        overall_score=30,
    )
    summary = outcome["session_summary"]
    assert summary["discussed_topics"] == 2
    assert summary["scored_topics"] == 2
    assert summary["total_topics"] == 5
    assert summary["overall_score"] == 30
