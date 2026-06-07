from app.services.learning.eligibility import filter_eligible_outcomes
from app.services.learning.session_comparison import build_session_comparison
from app.services.learning.session_summary import is_eligible_learning_outcome


def test_is_eligible_learning_outcome_requires_actual_discussion() -> None:
    assert is_eligible_learning_outcome(
        {
            "session_summary": {
                "discussed_topics": 0,
                "scored_topics": 0,
                "user_answer_rounds": 0,
            }
        }
    ) is False
    assert is_eligible_learning_outcome(
        {
            "session_summary": {
                "discussed_topics": 2,
                "scored_topics": 2,
                "user_answer_rounds": 4,
            }
        }
    ) is True


def test_filter_eligible_outcomes_skips_empty_sessions() -> None:
    rows = [
        {
            "outcome_json": {
                "session_id": "empty",
                "session_summary": {"discussed_topics": 0, "scored_topics": 0, "user_answer_rounds": 0},
            }
        },
        {
            "outcome_json": {
                "session_id": "real",
                "session_summary": {"discussed_topics": 2, "scored_topics": 2, "user_answer_rounds": 3},
            }
        },
    ]
    eligible = filter_eligible_outcomes(rows)
    assert [item["session_id"] for item in eligible] == ["real"]


def test_session_comparison_uses_previous_eligible_session_only() -> None:
    previous_empty = {
        "session_id": "empty",
        "completed_at": "2026-06-01",
        "session_summary": {
            "discussed_topics": 0,
            "scored_topics": 0,
            "signal_coverage_rate": 0.0,
            "overall_score": None,
            "user_answer_rounds": 0,
        },
    }
    previous_real = {
        "session_id": "real",
        "completed_at": "2026-06-02",
        "session_summary": {
            "discussed_topics": 3,
            "scored_topics": 2,
            "signal_coverage_rate": 0.5,
            "overall_score": 40,
            "user_answer_rounds": 6,
        },
    }
    current = {
        "session_id": "current",
        "completed_at": "2026-06-03",
        "session_summary": {
            "discussed_topics": 2,
            "scored_topics": 2,
            "signal_coverage_rate": 0.62,
            "overall_score": 30,
            "user_answer_rounds": 4,
        },
    }

    eligible = filter_eligible_outcomes(
        [
            {"outcome_json": previous_empty},
            {"outcome_json": previous_real},
            {"outcome_json": current},
        ]
    )
    assert [item["session_id"] for item in eligible] == ["real", "current"]

    comparison = build_session_comparison(
        current_outcome=current,
        previous_outcome=eligible[-2],
    )
    assert comparison is not None
    assert comparison["baseline_session_id"] == "real"
    assert comparison["discussed_coverage"]["baseline_count"] == 3
    assert len(comparison["points"]) == 3
