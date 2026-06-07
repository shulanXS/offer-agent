"""05 小步 3：Decide 消费 gaps + Act 自然过渡。"""
from __future__ import annotations

from typing import Any

from app.agent.interview.rule_fallback import build_rule_fallback_decision
from app.services.interview.actions import build_template_fallback_act_message


def _sample_topic() -> dict[str, Any]:
    return {
        "id": "topic-1",
        "name": "项目深挖",
        "objective": "验证项目经历",
        "dimension": "项目经历",
        "expected_signals": ["个人贡献", "结果指标"],
        "focus_points": ["技术难点"],
    }


def _runtime_state(**overrides: Any) -> dict[str, Any]:
    base = {
        "current_topic_probe_count": 0,
        "last_probed_information": "",
        "last_action": "opening",
    }
    base.update(overrides)
    return base


def _memory_with_gap(*, signal: str, covered: list[str] | None = None) -> dict[str, Any]:
    return {
        "relevant_memory": {
            "current_topic_id": "topic-1",
            "covered_signals": covered or [],
            "recent_evidence": (
                [{"topic_id": "topic-1", "matched_signal": covered[0], "quote": "个人贡献明确", "strength": 0.8}]
                if covered
                else []
            ),
        },
        "missing_information": [{"topic_id": "topic-1", "signal": signal, "from_plan": True}],
        "risks": [],
        "contradictions": [],
        "interview_knowledge": [],
    }


def _memory_fully_covered() -> dict[str, Any]:
    return {
        "relevant_memory": {
            "current_topic_id": "topic-1",
            "covered_signals": ["个人贡献", "结果指标"],
            "recent_evidence": [
                {"topic_id": "topic-1", "matched_signal": "个人贡献", "quote": "个人贡献明确", "strength": 0.8},
                {"topic_id": "topic-1", "matched_signal": "结果指标", "quote": "延迟降低30%", "strength": 0.7},
            ],
        },
        "missing_information": [],
        "risks": [],
        "contradictions": [],
        "interview_knowledge": [],
    }


def test_rule_fallback_probes_first_memory_gap() -> None:
    topic = _sample_topic()
    latest_answer = "我负责订单服务拆分和迁移，个人贡献比较明确，但还没讲指标。"
    decision = build_rule_fallback_decision(
        topic=topic,
        latest_answer=latest_answer,
        runtime_state=_runtime_state(),
        has_next_topic=True,
        memory_context=_memory_with_gap(signal="结果指标", covered=["个人贡献"]),
    )
    assert decision["action"] == "probe_metric"
    assert decision["expected_information"] == ["结果指标"]


def test_rule_fallback_advances_when_gaps_empty_and_covered() -> None:
    topic = _sample_topic()
    latest_answer = "我负责核心模块设计、开发、上线与结果验证，通过指标监控确保稳定性。"
    decision = build_rule_fallback_decision(
        topic=topic,
        latest_answer=latest_answer,
        runtime_state=_runtime_state(),
        has_next_topic=True,
        memory_context=_memory_fully_covered(),
    )
    assert decision["action"] == "next_topic"
    assert decision["expected_information"] == []


def test_rule_fallback_skips_last_probed_signal() -> None:
    topic = _sample_topic()
    memory_context = {
        "relevant_memory": {
            "current_topic_id": "topic-1",
            "covered_signals": ["个人贡献"],
            "recent_evidence": [
                {"topic_id": "topic-1", "matched_signal": "个人贡献", "quote": "个人贡献明确", "strength": 0.8}
            ],
        },
        "missing_information": [
            {"topic_id": "topic-1", "signal": "个人贡献", "from_plan": True},
            {"topic_id": "topic-1", "signal": "结果指标", "from_plan": True},
        ],
        "risks": [],
        "contradictions": [],
        "interview_knowledge": [],
    }
    decision = build_rule_fallback_decision(
        topic=topic,
        latest_answer="个人贡献明确，但指标还没展开。",
        runtime_state=_runtime_state(last_probed_information="个人贡献"),
        has_next_topic=True,
        memory_context=memory_context,
    )
    assert decision["expected_information"] == ["结果指标"]


def test_act_template_bridges_latest_answer_for_metric_gap() -> None:
    opening = "请先介绍一下你在订单系统项目中的具体职责。"
    latest_answer = "消息逻辑和表结构我独立负责，网络层和推送和团队协作完成。"
    message = build_template_fallback_act_message(
        "probe_metric",
        _sample_topic(),
        latest_answer=latest_answer,
        target_signal="结果指标",
        last_action="probe_ownership",
    )
    assert "指标" in message
    assert "独立" in message or "协作" in message or "团队" in message
    assert opening[:8] not in message


def test_rule_fallback_ignores_gaps_without_actionable_coverage() -> None:
    topic = _sample_topic()
    latest_answer = (
        "我负责核心模块设计、开发、上线与结果验证，通过指标监控和灰度发布确保稳定性，"
        "并沉淀了可复用方案。"
    )
    memory_context = {
        "relevant_memory": {"current_topic_id": "topic-1", "covered_signals": [], "recent_evidence": []},
        "missing_information": [{"topic_id": "topic-1", "signal": "个人贡献", "from_plan": True}],
        "risks": [],
        "contradictions": [],
        "interview_knowledge": [],
    }
    decision = build_rule_fallback_decision(
        topic=topic,
        latest_answer=latest_answer,
        runtime_state=_runtime_state(),
        has_next_topic=True,
        memory_context=memory_context,
    )
    assert decision["action"] == "next_topic"


def test_act_template_ownership_to_metric_scenario() -> None:
    latest_answer = "消息逻辑和表结构我独立负责，网络层和推送和团队协作完成。"
    message = build_template_fallback_act_message(
        "probe_metric",
        _sample_topic(),
        latest_answer=latest_answer,
        target_signal="结果指标",
        last_action="probe_ownership",
    )
    assert "想再补一下" in message or "指标" in message
    assert "你刚才提到对消息收发做了优化" not in message
