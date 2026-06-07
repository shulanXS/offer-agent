"""05 小步 2：Evidence Extraction、merge 与图节点。"""
from __future__ import annotations

from typing import Any

import pytest

from app.agent.interview.nodes.extract_evidence import extract_evidence_node
from app.agent.interview.nodes.merge_working_memory import merge_working_memory_node
from app.agent.interview.state import build_interview_reply_state
from app.services.interview.memory.extraction_schema import ExtractionValidationStats, validate_extraction_result
from app.services.interview.memory.merge import merge_extraction_into_working_memory
from app.services.interview.memory.project import project_evaluation_memory
from app.services.interview.memory.schema import empty_working_memory
from app.services.interview.reply_handler import InterviewReplyHandler


def _sample_plan() -> dict[str, Any]:
    return {
        "topics": [
            {
                "id": "topic-1",
                "name": "项目深挖",
                "objective": "验证项目经历",
                "expected_signals": ["个人贡献", "结果指标"],
                "focus_points": ["技术难点"],
                "required": True,
            },
            {
                "id": "topic-2",
                "name": "系统设计",
                "objective": "验证设计能力",
                "expected_signals": ["方案取舍"],
                "focus_points": [],
                "required": True,
            },
        ]
    }


def _sample_topic() -> dict[str, Any]:
    return _sample_plan()["topics"][0]


def test_validate_extraction_discards_plan_outside_signal() -> None:
    topic = _sample_topic()
    latest_answer = "我负责订单服务拆分和迁移，个人贡献比较明确。"
    raw = {
        "answer_quality": "partial",
        "claims": [],
        "evidence": [
            {
                "topic_id": "topic-1",
                "matched_signal": "自造信号",
                "polarity": "positive",
                "quote": "我负责订单服务拆分和迁移",
                "strength": 0.8,
            }
        ],
        "missing_information": [{"topic_id": "topic-1", "signal": "不存在的信号", "from_plan": True}],
        "risks": [],
        "potential_contradictions": [],
    }
    validated, stats = validate_extraction_result(
        raw,
        plan_json=_sample_plan(),
        current_topic=topic,
        latest_answer=latest_answer,
    )
    assert validated["evidence"] == []
    assert validated["missing_information"] == []
    assert stats.discarded_evidence == 1
    assert stats.discarded_missing == 1


def test_validate_extraction_requires_quote_from_latest_answer() -> None:
    topic = _sample_topic()
    latest_answer = "我负责订单服务拆分和迁移。"
    raw = {
        "answer_quality": "partial",
        "claims": [],
        "evidence": [
            {
                "topic_id": "topic-1",
                "matched_signal": "个人贡献",
                "polarity": "positive",
                "quote": "候选人从未说过的内容",
                "strength": 0.8,
            }
        ],
        "missing_information": [],
        "risks": [],
        "potential_contradictions": [],
    }
    validated, stats = validate_extraction_result(
        raw,
        plan_json=_sample_plan(),
        current_topic=topic,
        latest_answer=latest_answer,
    )
    assert validated["evidence"] == []
    assert stats.discarded_evidence == 1


def test_merge_keeps_existing_memory_when_extraction_empty() -> None:
    plan_json = _sample_plan()
    existing = empty_working_memory()
    existing["claims"] = [{"topic_id": "topic-1", "content": "已有声明", "status": "unverified"}]
    merged, stats = merge_extraction_into_working_memory(
        working_memory=existing,
        extraction=None,
        plan_json=plan_json,
        current_topic_id="topic-1",
    )
    assert merged["claims"] == existing["claims"]
    assert stats.degraded is True
    assert merged["missing_information"]
    assert all(item["from_plan"] is True for item in merged["missing_information"])


def test_merge_does_not_corrupt_on_invalid_items() -> None:
    plan_json = _sample_plan()
    existing = empty_working_memory()
    extraction = {
        "answer_quality": "partial",
        "claims": [{"topic_id": "topic-9", "content": "无效", "status": "unverified"}],
        "evidence": [
            {
                "topic_id": "topic-1",
                "matched_signal": "个人贡献",
                "polarity": "positive",
                "quote": "未出现",
                "strength": 0.9,
            }
        ],
        "missing_information": [],
        "risks": ["风险 A"],
        "potential_contradictions": [],
    }
    validated, _ = validate_extraction_result(
        extraction,
        plan_json=plan_json,
        current_topic=_sample_topic(),
        latest_answer="我负责模块 A。",
    )
    merged, _stats = merge_extraction_into_working_memory(
        working_memory=existing,
        extraction=validated,
        plan_json=plan_json,
        current_topic_id="topic-1",
    )
    assert merged["evidence"] == []
    assert merged["claims"] == []
    assert merged["risks"] == ["风险 A"]
    assert any(item["signal"] == "个人贡献" for item in merged["missing_information"])


def test_merge_adds_valid_evidence_and_recomputes_missing() -> None:
    plan_json = _sample_plan()
    topic = _sample_topic()
    latest_answer = "我负责订单服务拆分和迁移，个人贡献比较明确。"
    raw = {
        "answer_quality": "strong",
        "claims": [{"topic_id": "topic-1", "content": "负责订单服务拆分和迁移", "status": "unverified"}],
        "evidence": [
            {
                "topic_id": "topic-1",
                "matched_signal": "个人贡献",
                "polarity": "positive",
                "quote": "个人贡献比较明确",
                "strength": 0.8,
                "rationale": "明确个人贡献",
            }
        ],
        "missing_information": [],
        "risks": [],
        "potential_contradictions": [],
    }
    validated, _ = validate_extraction_result(
        raw,
        plan_json=plan_json,
        current_topic=topic,
        latest_answer=latest_answer,
    )
    merged, stats = merge_extraction_into_working_memory(
        working_memory=empty_working_memory(),
        extraction=validated,
        plan_json=plan_json,
        current_topic_id="topic-1",
    )
    assert stats.merged_evidence == 1
    assert merged["evidence"][0]["matched_signal"] == "个人贡献"
    assert not any(item["signal"] == "个人贡献" for item in merged["missing_information"])
    assert any(item["signal"] == "结果指标" for item in merged["missing_information"])


def test_project_evaluation_memory_groups_by_topic() -> None:
    plan_json = _sample_plan()
    working_memory = empty_working_memory()
    working_memory["evidence"] = [
        {
            "topic_id": "topic-1",
            "matched_signal": "个人贡献",
            "polarity": "positive",
            "quote": "个人贡献明确",
            "strength": 0.8,
        }
    ]
    projected = project_evaluation_memory(plan_json=plan_json, working_memory=working_memory)
    assert "topic-1" in projected["evidence_by_topic"]
    assert "个人贡献" in projected["evidence_by_topic"]["topic-1"]["covered_signals"]
    assert "结果指标" in projected["evidence_by_topic"]["topic-1"]["missing_signals"]


def _build_graph_test_state(*, plan_json, topic, latest_answer):
    runtime_state = {
        "current_topic_id": topic["id"],
        "topic_summaries": {},
        "working_memory": empty_working_memory(),
        "answer_round": 1,
        "current_topic_round": 1,
        "current_topic_probe_count": 0,
        "last_probed_information": "",
        "last_action": "opening",
        "completed_topic_ids": [],
    }
    state = build_interview_reply_state(
        trace_id="trace-graph",
        plan_json=plan_json,
        configuration={"interview_type": "experienced"},
        resume=None,
        runtime_state=runtime_state,
        current_topic=topic,
        all_messages=[
            {"role": "assistant", "content": "请介绍项目", "meta": {"topic_id": topic["id"]}},
            {"role": "user", "content": latest_answer, "meta": {"topic_id": topic["id"]}},
        ],
        latest_answer=latest_answer,
    )
    state["current_topic_id"] = topic["id"]
    state["interview_type"] = "experienced"
    state["topic_messages"] = state["all_messages"]
    state["has_next_topic"] = True
    state["following_topic"] = plan_json["topics"][1]
    return state


def _fake_valid_extraction(*, plan_json, topic, latest_answer):
    raw = {
        "answer_quality": "partial",
        "claims": [],
        "evidence": [
            {
                "topic_id": topic["id"],
                "matched_signal": "个人贡献",
                "polarity": "positive",
                "quote": "个人贡献比较明确",
                "strength": 0.7,
            }
        ],
        "missing_information": [],
        "risks": [],
        "potential_contradictions": [],
    }
    validated, _stats = validate_extraction_result(
        raw,
        plan_json=plan_json,
        current_topic=topic,
        latest_answer=latest_answer,
    )
    return validated


def test_graph_invoke_persists_working_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    plan_json = _sample_plan()
    topic = plan_json["topics"][0]
    latest_answer = "我负责订单服务拆分和迁移，个人贡献比较明确。"

    def _fake_extract(*_args, **_kwargs):
        return _fake_valid_extraction(plan_json=plan_json, topic=topic, latest_answer=latest_answer), ExtractionValidationStats()

    monkeypatch.setattr(
        "app.agent.interview.nodes.extract_evidence._extractor.extract",
        _fake_extract,
    )

    state = _build_graph_test_state(plan_json=plan_json, topic=topic, latest_answer=latest_answer)
    after_extract = extract_evidence_node(state)
    after_merge = merge_working_memory_node(after_extract)

    working_memory = after_merge["runtime_state"]["working_memory"]
    assert len(working_memory["evidence"]) == 1
    assert after_merge["memory_context"]["relevant_memory"]["covered_signals"] == ["个人贡献"]
    assert after_merge["memory_context"]["missing_information"]


def test_reply_handler_roundtrip_persists_working_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    plan_json = _sample_plan()
    topic = plan_json["topics"][0]
    latest_answer = "我负责订单服务拆分和迁移，个人贡献比较明确。"

    def _fake_extract(*_args, **_kwargs):
        return _fake_valid_extraction(plan_json=plan_json, topic=topic, latest_answer=latest_answer), ExtractionValidationStats()

    monkeypatch.setattr(
        "app.agent.interview.nodes.extract_evidence._extractor.extract",
        _fake_extract,
    )

    handler = InterviewReplyHandler()
    outcome = handler.process(
        plan_json=plan_json,
        configuration={"interview_type": "experienced"},
        resume=None,
        runtime_state={
            "current_topic_id": topic["id"],
            "topic_summaries": {},
            "working_memory": empty_working_memory(),
            "answer_round": 0,
            "current_topic_round": 0,
            "current_topic_probe_count": 0,
            "last_probed_information": "",
            "last_action": "opening",
            "completed_topic_ids": [],
            "deadline_at": "2099-01-01T00:00:00+00:00",
        },
        current_topic=topic,
        all_messages=[
            {"role": "assistant", "content": "请介绍项目", "meta": {"topic_id": topic["id"]}},
            {"role": "user", "content": latest_answer, "meta": {"topic_id": topic["id"]}},
        ],
        latest_answer=latest_answer,
        trace_id="trace-handler",
    )
    assert len(outcome.runtime_state["working_memory"]["evidence"]) == 1
