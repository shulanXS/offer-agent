from app.services.interview.actions import normalize_decision


def test_normalize_decision_rejects_unknown_action() -> None:
    decision = normalize_decision(
        {"action": "invalid_action", "should_change_topic": True},
        current_topic_id="topic-1",
        has_next_topic=True,
    )
    assert decision["action"] == "next_topic"


def test_normalize_decision_maps_finish_to_next_when_more_topics() -> None:
    decision = normalize_decision(
        {"action": "finish", "should_change_topic": True},
        current_topic_id="topic-1",
        has_next_topic=True,
    )
    assert decision["action"] == "next_topic"


def test_normalize_decision_keeps_probe_on_current_topic() -> None:
    decision = normalize_decision(
        {
            "action": "probe_ownership",
            "target_topic_id": "topic-2",
            "reason": "缺贡献",
            "expected_information": ["个人职责"],
            "should_change_topic": True,
        },
        current_topic_id="topic-1",
        has_next_topic=True,
    )
    assert decision["action"] == "probe_ownership"
    assert decision["target_topic_id"] == "topic-1"
    assert decision["should_change_topic"] is False
