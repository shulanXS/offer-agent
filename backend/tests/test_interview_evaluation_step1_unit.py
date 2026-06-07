from app.services.interview_evaluation.context import group_messages_by_topic
from app.services.interview_evaluation.minimal_report import build_minimal_evaluation_report
from app.services.interview.memory.schema import empty_working_memory


def _sample_plan() -> dict:
    return {
        "topics": [
            {
                "id": "topic-1",
                "name": "项目深挖",
                "dimension": "项目经历",
                "expected_signals": ["个人贡献", "结果指标"],
                "evaluation_criteria": "是否能说明个人贡献与结果",
            },
            {
                "id": "topic-2",
                "name": "系统设计",
                "dimension": "方案取舍",
                "expected_signals": ["备选方案"],
                "evaluation_criteria": "是否能说明方案取舍",
            },
        ]
    }


def test_group_messages_by_topic() -> None:
    plan_json = _sample_plan()
    messages = [
        {"role": "assistant", "content": "请介绍项目", "meta": {"topic_id": "topic-1"}},
        {"role": "user", "content": "我负责核心模块", "meta": {"topic_id": "topic-1"}},
        {"role": "assistant", "content": "如何设计", "meta": {"topic_id": "topic-2"}},
    ]
    grouped = group_messages_by_topic(messages, plan_json=plan_json)
    assert len(grouped["topic-1"]) == 2
    assert len(grouped["topic-2"]) == 1


def test_minimal_report_separates_risks_and_unverified() -> None:
    working_memory = empty_working_memory()
    working_memory["evidence"] = [
        {
            "topic_id": "topic-1",
            "matched_signal": "个人贡献",
            "polarity": "positive",
            "quote": "我负责核心模块设计",
            "strength": 0.8,
        }
    ]
    working_memory["risks"] = ["项目规模描述前后不一致"]
    working_memory["claims"] = [
        {"topic_id": "topic-2", "content": "尚未验证的系统设计能力", "status": "unverified"},
    ]
    evaluation_context = {
        "evidence_by_topic": {
            "topic-1": {"evidence": working_memory["evidence"], "covered_signals": ["个人贡献"], "missing_signals": []},
            "topic-2": {"evidence": [], "covered_signals": [], "missing_signals": ["备选方案"]},
        },
        "risks": working_memory["risks"],
        "unverified_items": working_memory["claims"],
    }
    report = build_minimal_evaluation_report(
        plan_json=_sample_plan(),
        configuration={"interview_type": "experienced"},
        runtime_state={"completed_topic_ids": ["topic-1"], "working_memory": working_memory},
        evaluation_context=evaluation_context,
    )
    assert report["source"] == "rule_minimal"
    assert report["coverage"]["completed_topic_count"] == 1
    assert report["coverage"]["total_topic_count"] == 2
    assert report["risks"] == ["项目规模描述前后不一致"]
    assert report["unverified_items"][0]["content"] == "尚未验证的系统设计能力"
    assert "尚未验证" in report["summary"] or report["unverified_items"]
