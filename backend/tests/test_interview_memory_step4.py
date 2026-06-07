"""05 小步 4：潜在矛盾检测与验证性追问。"""
from __future__ import annotations

from typing import Any

import pytest

from app.agent.interview.nodes.decide_node import decide_node
from app.agent.interview.nodes.merge_working_memory import merge_working_memory_node
from app.agent.interview.rule_fallback import build_rule_fallback_decision
from app.agent.interview.state import build_interview_reply_state
from app.services.interview.actions import build_template_fallback_act_message
from app.services.interview.memory.contradictions import (
    detect_potential_contradictions,
    sanitize_contradiction_description,
)
from app.services.interview.memory.extraction_schema import validate_extraction_result
from app.services.interview.memory.merge import merge_extraction_into_working_memory
from app.services.interview.memory.project import project_evaluation_memory
from app.services.interview.memory.schema import empty_working_memory


def _sample_plan() -> dict[str, Any]:
    return {
        "topics": [
            {
                "id": "topic-1",
                "name": "项目深挖",
                "expected_signals": ["个人贡献", "结果指标"],
                "focus_points": [],
            }
        ]
    }


def _sample_topic() -> dict[str, Any]:
    return _sample_plan()["topics"][0]


def test_detect_polarity_conflict_on_same_signal() -> None:
    existing = empty_working_memory()
    existing["evidence"] = [
        {
            "topic_id": "topic-1",
            "matched_signal": "个人贡献",
            "polarity": "positive",
            "quote": "我独立负责消息模块",
            "strength": 0.8,
        }
    ]
    findings = detect_potential_contradictions(
        existing_memory=existing,
        new_claims=[],
        new_evidence=[
            {
                "topic_id": "topic-1",
                "matched_signal": "个人贡献",
                "polarity": "negative",
                "quote": "这部分主要是团队协作完成",
                "strength": 0.7,
            }
        ],
        current_topic_id="topic-1",
    )
    assert findings
    assert "撒谎" not in findings[0]["description"]
    assert findings[0]["status"] == "unverified"


def test_sanitize_contradiction_removes_accusatory_words() -> None:
    text = sanitize_contradiction_description("候选人可能在撒谎")
    assert "撒谎" not in text
    assert "待核实" in text


def test_merge_persists_detected_contradictions() -> None:
    plan_json = _sample_plan()
    existing = empty_working_memory()
    existing["evidence"] = [
        {
            "topic_id": "topic-1",
            "matched_signal": "个人贡献",
            "polarity": "positive",
            "quote": "我独立负责消息模块",
            "strength": 0.8,
        }
    ]
    extraction = {
        "answer_quality": "partial",
        "claims": [],
        "evidence": [
            {
                "topic_id": "topic-1",
                "matched_signal": "个人贡献",
                "polarity": "negative",
                "quote": "这部分主要是团队协作完成",
                "strength": 0.7,
            }
        ],
        "missing_information": [],
        "risks": [],
        "potential_contradictions": [],
    }
    validated, _ = validate_extraction_result(
        extraction,
        plan_json=plan_json,
        current_topic=_sample_topic(),
        latest_answer="这部分主要是团队协作完成。",
    )
    merged, stats = merge_extraction_into_working_memory(
        working_memory=existing,
        extraction=validated,
        plan_json=plan_json,
        current_topic_id="topic-1",
    )
    assert stats.merged_contradictions >= 1
    assert merged["contradictions"]


def test_rule_fallback_verification_probe_once() -> None:
    topic = _sample_topic()
    memory_context = {
        "relevant_memory": {"current_topic_id": "topic-1", "covered_signals": ["个人贡献"], "recent_evidence": []},
        "missing_information": [{"topic_id": "topic-1", "signal": "结果指标", "from_plan": True}],
        "contradictions": [
            {
                "topic_id": "topic-1",
                "description": "前后表述待核实：独立与协作说法不一致",
                "status": "unverified",
            }
        ],
        "risks": [],
        "interview_knowledge": [],
    }
    runtime_state = {"current_topic_probe_count": 0, "last_probed_information": "", "contradiction_verification_used": False}
    first = build_rule_fallback_decision(
        topic=topic,
        latest_answer="我独立负责模块，但也说主要是团队协作。",
        runtime_state=runtime_state,
        has_next_topic=True,
        memory_context=memory_context,
    )
    assert first["action"] == "probe_detail"
    assert first["_verify_contradiction"] is True

    runtime_state["contradiction_verification_used"] = True
    second = build_rule_fallback_decision(
        topic=topic,
        latest_answer="我独立负责模块，但也说主要是团队协作。",
        runtime_state=runtime_state,
        has_next_topic=True,
        memory_context=memory_context,
    )
    assert second.get("_verify_contradiction") is not True
    assert second["action"] == "probe_metric"


def test_decide_node_marks_verification_used() -> None:
    topic = _sample_topic()
    state = build_interview_reply_state(
        trace_id="trace-verify",
        plan_json=_sample_plan(),
        configuration={"interview_type": "experienced"},
        resume=None,
        runtime_state={
            "current_topic_id": topic["id"],
            "topic_summaries": {},
            "working_memory": empty_working_memory(),
            "contradiction_verification_used": False,
            "current_topic_probe_count": 0,
            "last_probed_information": "",
        },
        current_topic=topic,
        all_messages=[],
        latest_answer="我独立负责，也主要是团队协作。",
    )
    state["current_topic_id"] = topic["id"]
    state["has_next_topic"] = True
    state["memory_context"] = {
        "relevant_memory": {"current_topic_id": topic["id"], "covered_signals": [], "recent_evidence": []},
        "missing_information": [],
        "contradictions": [
            {"topic_id": topic["id"], "description": "前后表述待核实", "status": "unverified"}
        ],
        "risks": [],
        "interview_knowledge": [],
    }
    state["observe_context"] = {"context_topic_messages": []}

    def _fake_decide(**_kwargs):
        return {
            "action": "probe_detail",
            "target_topic_id": topic["id"],
            "reason": "待核实前后表述是否一致",
            "expected_information": ["澄清：前后表述待核实"],
            "should_change_topic": False,
            "_verify_contradiction": True,
        }

    pytest.importorskip("unittest")
    from unittest.mock import patch

    with patch("app.agent.interview.nodes.decide_node.decide_agent.decide", side_effect=_fake_decide):
        result = decide_node(state)
    assert result["runtime_state"]["contradiction_verification_used"] is True


def test_project_includes_unverified_contradictions() -> None:
    working_memory = empty_working_memory()
    working_memory["contradictions"] = [
        {"topic_id": "topic-1", "description": "前后表述待核实", "status": "unverified"}
    ]
    working_memory["claims"] = [{"topic_id": "topic-1", "content": "负责模块", "status": "unverified"}]
    projected = project_evaluation_memory(plan_json=_sample_plan(), working_memory=working_memory)
    assert projected["contradictions"]
    assert projected["unverified_items"]
    assert any("待核实" in risk for risk in projected["risks"])


def test_verification_template_is_neutral() -> None:
    message = build_template_fallback_act_message(
        "probe_detail",
        _sample_topic(),
        latest_answer="我独立负责消息模块，后来也提到主要是团队协作。",
        target_signal="澄清：前后表述待核实：独立与协作",
        verify_contradiction=True,
    )
    assert "想确认一下" in message
    assert "撒谎" not in message
    assert "独立" in message or "协作" in message
