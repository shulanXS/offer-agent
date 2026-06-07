from app.services.interview_evaluation.feedback_items import (
    feedback_item_from_legacy_text,
    make_feedback_item,
    normalize_feedback_list,
)


def test_normalize_feedback_list_accepts_structured_items() -> None:
    items = normalize_feedback_list(
        [
            {"title": "项目深挖", "body": "你提到个人负责范围，表达较清楚。"},
            {"title": "项目深挖", "body": "重复项"},
        ],
        limit=3,
    )
    assert len(items) == 1
    assert items[0]["title"] == "项目深挖"


def test_normalize_feedback_list_converts_legacy_strings() -> None:
    items = normalize_feedback_list(
        ["「Redis 基础」回答深度不够，关键考察点尚未讲清楚。"],
        limit=3,
    )
    assert items[0]["title"] == "Redis 基础"
    assert "回答深度不够" in items[0]["body"]


def test_feedback_item_from_legacy_text_uses_bracket_title() -> None:
    item = feedback_item_from_legacy_text("「IM 消息系统」Socket 细节尚未讲透。")
    assert item == make_feedback_item(title="IM 消息系统", body="Socket 细节尚未讲透。")
