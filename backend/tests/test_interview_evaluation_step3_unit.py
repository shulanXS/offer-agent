from app.services.interview_evaluation.jd_match import build_jd_match, extract_jd_requirements, extract_plan_jd_alignments


def _sample_plan() -> dict:
    return {
        "topics": [
            {
                "id": "topic-1",
                "name": "Java 微服务",
                "dimension": "后端开发",
                "objective": "验证微服务开发与治理经验",
                "expected_signals": ["微服务经验"],
                "source_refs": ["jd:熟悉 Java 微服务开发"],
            },
            {
                "id": "topic-2",
                "name": "系统设计",
                "dimension": "方案取舍",
                "expected_signals": ["备选方案"],
                "source_refs": ["resume:订单系统"],
            },
            {
                "id": "topic-3",
                "name": "Agent 核心能力",
                "dimension": "技术深度",
                "expected_signals": ["任务规划"],
                "source_refs": ["jd:agent_core_abilities"],
            },
        ]
    }


def test_build_jd_match_returns_none_without_jd() -> None:
    result = build_jd_match(
        configuration={"jd_text": ""},
        plan_json=_sample_plan(),
        evaluation_context={"evidence_by_topic": {}, "risks": []},
        competencies=[],
    )
    assert result is None


def test_extract_plan_jd_alignments_uses_topic_name_for_slug_refs() -> None:
    alignments = extract_plan_jd_alignments(_sample_plan())
    assert len(alignments) == 2
    by_topic = {item["topic_id"]: item for item in alignments}
    assert by_topic["topic-1"]["display_requirement"] == "熟悉 Java 微服务开发"
    assert by_topic["topic-3"]["display_requirement"] == "Agent 核心能力"


def test_extract_jd_requirements_only_from_plan_topics() -> None:
    requirements = extract_jd_requirements(
        "负责高并发订单系统\n熟悉 Spring Cloud",
        _sample_plan(),
    )
    texts = [item["requirement"] for item in requirements]
    assert "熟悉 Java 微服务开发" in texts
    assert "Agent 核心能力" in texts
    assert "负责高并发订单系统" not in texts
    assert "熟悉 Spring Cloud" not in texts


def test_jd_match_classifies_aligned_and_unverified() -> None:
    plan_json = _sample_plan()
    competencies = [
        {
            "topic_id": "topic-1",
            "name": "Java 微服务",
            "dimension": "后端开发",
            "status": "verified",
            "score": 4,
            "confidence": 0.8,
            "strengths": [],
            "risks": [],
            "evidence_references": [],
        },
        {
            "topic_id": "topic-3",
            "name": "Agent 核心能力",
            "dimension": "技术深度",
            "status": "unverified",
            "score": None,
            "confidence": 0.25,
            "strengths": [],
            "risks": [],
            "evidence_references": [],
        },
    ]
    evaluation_context = {
        "evidence_by_topic": {
            "topic-1": {
                "evidence": [
                    {
                        "topic_id": "topic-1",
                        "matched_signal": "微服务经验",
                        "polarity": "positive",
                        "quote": "我负责 Java 微服务核心模块开发",
                        "strength": 0.85,
                    }
                ],
                "covered_signals": ["微服务经验"],
                "missing_signals": [],
            },
            "topic-3": {"evidence": [], "covered_signals": [], "missing_signals": ["任务规划"]},
        },
        "risks": [],
    }
    jd_match = build_jd_match(
        configuration={"jd_text": "熟悉 Java 微服务开发\n熟悉分布式系统设计"},
        plan_json=plan_json,
        evaluation_context=evaluation_context,
        competencies=competencies,
    )
    assert jd_match is not None
    assert jd_match["has_jd"] is True
    assert jd_match["requirement_count"] == 2
    assert len(jd_match["verified_aligned"]) == 1
    assert len(jd_match["unverified"]) == 1
    assert "本场对齐 2 条 JD 要点" in jd_match["summary"]
    assert jd_match["unverified"][0]["note"] == "本场未充分讨论该主题。"


def test_jd_match_marks_risk_when_partially_verified() -> None:
    jd_match = build_jd_match(
        configuration={"jd_text": "熟悉 Java 微服务开发"},
        plan_json=_sample_plan(),
        evaluation_context={
            "evidence_by_topic": {
                "topic-1": {
                    "evidence": [
                        {
                            "topic_id": "topic-1",
                            "matched_signal": "微服务经验",
                            "polarity": "positive",
                            "quote": "我做过 Java 微服务开发",
                            "strength": 0.7,
                        },
                        {
                            "topic_id": "topic-1",
                            "matched_signal": "微服务经验",
                            "polarity": "negative",
                            "quote": "但微服务拆分边界描述前后不一致",
                            "strength": 0.6,
                        },
                    ],
                    "covered_signals": ["微服务经验"],
                    "missing_signals": [],
                }
            },
            "risks": ["微服务拆分边界描述前后不一致"],
        },
        competencies=[
            {
                "topic_id": "topic-1",
                "name": "Java 微服务",
                "dimension": "后端开发",
                "status": "partially_verified",
                "score": 3,
                "confidence": 0.6,
                "strengths": [],
                "risks": ["拆分边界描述不一致"],
                "evidence_references": [],
            }
        ],
    )
    assert jd_match is not None
    assert jd_match["verified_with_risk"]
    assert not jd_match["verified_aligned"]
    assert jd_match["verified_with_risk"][0]["note"] == "拆分边界描述不一致"


def test_jd_match_empty_when_plan_has_no_jd_topics() -> None:
    plan_json = {
        "topics": [
            {
                "id": "topic-1",
                "name": "项目深挖",
                "source_refs": ["resume:demo"],
            }
        ]
    }
    jd_match = build_jd_match(
        configuration={"jd_text": "负责高并发系统\n熟悉 K8s"},
        plan_json=plan_json,
        evaluation_context={"evidence_by_topic": {}, "risks": []},
        competencies=[],
    )
    assert jd_match is not None
    assert jd_match["requirement_count"] == 0
    assert "未标注与 JD 对应" in jd_match["summary"]
