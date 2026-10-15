"""域 2.1 验证：trim-mean / 浮点分 / 0/1 评分边界。"""
from __future__ import annotations

from app.services.interview_evaluation.aggregate import compute_overall_score
from app.services.interview_evaluation.competencies import _derive_score


def test_two_scores_no_overall() -> None:
    """2 个评分时 overall_score=None（避免"二点评分 = 70"误导）。"""
    comps = [
        {"topic_id": "t1", "status": "verified", "score": 3.0},
        {"topic_id": "t2", "status": "verified", "score": 4.0},
    ]
    assert compute_overall_score(comps) is None


def test_one_score_returns_none() -> None:
    """1 个评分时返回 None。"""
    comps = [
        {"topic_id": "t1", "status": "verified", "score": 4.0},
    ]
    assert compute_overall_score(comps) is None


def test_zero_scores_returns_none() -> None:
    comps = [
        {"topic_id": "t1", "status": "unverified", "score": None},
    ]
    assert compute_overall_score(comps) is None


def test_three_scores_trim_mean() -> None:
    comps = [
        {"topic_id": "t1", "status": "verified", "score": 5.0},
        {"topic_id": "t2", "status": "verified", "score": 3.0},
        {"topic_id": "t3", "status": "verified", "score": 4.0},
    ]
    # 排序 [3, 4, 5]，trim 后 [4]，4/5*100 = 80
    assert compute_overall_score(comps) == 80


def test_four_scores_trim_mean() -> None:
    comps = [
        {"topic_id": "t1", "status": "verified", "score": 5.0},
        {"topic_id": "t2", "status": "verified", "score": 3.0},
        {"topic_id": "t3", "status": "verified", "score": 4.0},
        {"topic_id": "t4", "status": "verified", "score": 2.0},
    ]
    # 排序 [2, 3, 4, 5]，trim 后 [3, 4]，avg=3.5 → 3.5/5*100=70
    assert compute_overall_score(comps) == 70


def test_competency_score_float_legal() -> None:
    """1.5 / 2.5 这种浮点分合法。"""
    score = _derive_score(
        status="verified",
        evidence=[
            {"strength": 0.5, "polarity": "positive"},
            {"strength": 0.5, "polarity": "positive"},
        ],
        covered={"a", "b"},
        expected=["a", "b"],
    )
    assert score is not None
    assert 1.0 <= score <= 5.0
    # 浮点保留 0.5 步进（即 2 位小数）
    assert round(score, 2) == score


def test_competency_score_unverified_is_none() -> None:
    score = _derive_score(
        status="unverified",
        evidence=[],
        covered=set(),
        expected=["a", "b"],
    )
    assert score is None


def test_competency_score_clamped() -> None:
    """即便 base 计算溢出，1.0–5.0 钳制。"""
    score = _derive_score(
        status="verified",
        evidence=[{"strength": 0.0, "polarity": "negative"}] * 10,
        covered=set(),
        expected=["a"],
    )
    assert score is not None
    assert 1.0 <= score <= 5.0
