from app.services.interview_evaluation.evidence_references import (
    build_answer_rounds,
    build_competency_answer_rounds,
    build_evidence_references,
    find_round_for_quote,
    find_latest_round_for_quote,
)


def test_build_answer_rounds_pairs_questions_with_answers() -> None:
    messages = [
        {"role": "assistant", "content": "请介绍项目职责", "meta": {"topic_id": "topic-1"}},
        {"role": "user", "content": "我负责消息收发模块", "meta": {"topic_id": "topic-1"}},
        {"role": "assistant", "content": "Socket 长连接如何实现？", "meta": {"topic_id": "topic-1"}},
        {"role": "user", "content": "没有全权负责，只是协作", "meta": {"topic_id": "topic-1"}},
    ]
    rounds = build_answer_rounds(messages)
    assert len(rounds) == 2
    assert rounds[0]["question"] == "请介绍项目职责"
    assert rounds[0]["answer"] == "我负责消息收发模块"
    assert rounds[1]["question"] == "Socket 长连接如何实现？"


def test_find_round_for_quote_prefers_shortest_matching_answer() -> None:
    rounds = build_answer_rounds(
        [
            {"role": "assistant", "content": "第一问"},
            {"role": "user", "content": "我负责消息收发模块，没有全权负责网络层"},
            {"role": "assistant", "content": "第二问"},
            {"role": "user", "content": "没有全权负责，只是协作"},
        ]
    )
    matched = find_round_for_quote("没有全权负责", rounds)
    assert matched is not None
    assert matched["answer"] == "没有全权负责，只是协作"


def test_build_evidence_references_links_quote_to_question_and_sorts_chronologically() -> None:
    messages = [
        {"role": "assistant", "content": "请介绍职责与后端理解"},
        {"role": "user", "content": "独立负责消息收发核心逻辑"},
        {"role": "assistant", "content": "Socket 长连接如何实现？"},
        {"role": "user", "content": "没有全权负责，只是协作"},
    ]
    evidence = [
        {
            "topic_id": "topic-1",
            "matched_signal": "Socket 长连接经验",
            "polarity": "negative",
            "quote": "没有全权负责",
            "strength": 0.7,
        },
        {
            "topic_id": "topic-1",
            "matched_signal": "个人职责",
            "polarity": "positive",
            "quote": "独立负责消息收发核心逻辑",
            "strength": 0.8,
        },
    ]
    references = build_evidence_references(evidence, messages)
    assert len(references) == 2
    assert references[0]["question"] == "请介绍职责与后端理解"
    assert references[0]["answer"] == "独立负责消息收发核心逻辑"
    assert references[1]["question"] == "Socket 长连接如何实现？"
    assert references[1]["answer"] == "没有全权负责，只是协作"


def test_build_evidence_references_drops_quotes_not_in_user_messages() -> None:
    messages = [
        {"role": "assistant", "content": "请介绍职责"},
        {"role": "user", "content": "独立负责消息收发核心逻辑"},
    ]
    evidence = [
        {
            "topic_id": "topic-1",
            "matched_signal": "个人职责",
            "polarity": "positive",
            "quote": "独立负责消息收发核心逻辑",
            "strength": 0.8,
        },
        {
            "topic_id": "topic-1",
            "matched_signal": "Socket 长连接经验",
            "polarity": "negative",
            "quote": "没有全权负责",
            "strength": 0.7,
        },
    ]
    references = build_evidence_references(evidence, messages)
    assert len(references) == 1
    assert references[0]["quote"] == "独立负责消息收发核心逻辑"


def test_find_latest_round_for_quote_prefers_most_recent_answer() -> None:
    rounds = build_answer_rounds(
        [
            {"role": "assistant", "content": "第一问"},
            {"role": "user", "content": "我负责消息收发模块"},
            {"role": "assistant", "content": "第二问"},
            {"role": "user", "content": "我负责消息收发模块，并补充了联调细节"},
        ]
    )
    matched = find_latest_round_for_quote("我负责消息收发模块", rounds)
    assert matched is not None
    assert matched["answer"] == "我负责消息收发模块，并补充了联调细节"


def test_build_competency_answer_rounds_includes_all_user_answers() -> None:
    messages = [
        {"role": "assistant", "content": "请介绍职责"},
        {"role": "user", "content": "独立负责消息收发核心逻辑"},
        {"role": "assistant", "content": "Socket 长连接如何实现？"},
        {"role": "user", "content": "没有全权负责，只是协作"},
        {"role": "assistant", "content": "具体如何协作？"},
        {"role": "user", "content": "与后端联调接口定义"},
    ]
    evidence = [
        {
            "topic_id": "topic-1",
            "matched_signal": "个人职责",
            "polarity": "positive",
            "quote": "独立负责消息收发核心逻辑",
            "strength": 0.8,
        },
        {
            "topic_id": "topic-1",
            "matched_signal": "Socket 长连接经验",
            "polarity": "negative",
            "quote": "没有全权负责",
            "strength": 0.7,
        },
    ]
    rounds = build_competency_answer_rounds(evidence, messages)
    assert len(rounds) == 3
    assert rounds[0]["answer"] == "独立负责消息收发核心逻辑"
    assert len(rounds[0]["evidence_items"]) == 1
    assert rounds[1]["answer"] == "没有全权负责，只是协作"
    assert len(rounds[1]["evidence_items"]) == 1
    assert rounds[2]["answer"] == "与后端联调接口定义"
    assert rounds[2]["evidence_items"] == []
