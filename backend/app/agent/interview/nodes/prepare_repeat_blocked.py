"""重复追问同一缺失信息时强制切题。"""
from __future__ import annotations

from app.agent.interview.state import InterviewReplyState


def prepare_repeat_blocked_node(state: InterviewReplyState) -> InterviewReplyState:
    return {
        **state,
        "decision": {
            "action": "next_topic",
            "target_topic_id": state["current_topic_id"],
            "reason": "repeat_probe_blocked",
            "expected_information": [],
            "should_change_topic": True,
        },
    }
