from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_interview_options_returns_fixed_enums() -> None:
    # v1.1: 显式传 Accept-Language=zh，因为默认 fallback 是 en
    response = client.get("/api/interview-options", headers={"Accept-Language": "zh"})

    assert response.status_code == 200
    payload = response.json()
    # v2.2: duration 与 max_focus_topics 已扩展
    assert payload["duration_minutes"] == 45
    assert payload["max_focus_topics"] == 8
    assert payload["duration_minutes_options"] == [15, 30, 45, 60]
    assert payload["include_algorithm_supported"] is True
    # v2.2: interview_types 多一项 intern
    assert payload["interview_types"] == [
        {"value": "intern", "label": "实习"},
        {"value": "campus", "label": "校招"},
        {"value": "experienced", "label": "社招"},
    ]
    # v2.2: target_roles 扩到 9 项 + custom 槽位
    role_values = [item["value"] for item in payload["target_roles"]]
    assert "frontend" in role_values
    assert "backend" in role_values
    assert "fullstack" in role_values
    assert "agent" in role_values
    assert "data_ml" in role_values
    assert "mobile" in role_values
    assert "qa" in role_values
    assert "sre" in role_values
    assert "embedded" in role_values
    assert "__custom__" in role_values
    assert [item["value"] for item in payload["languages"]] == ["java", "python", "go", "javascript"]
    assert [item["value"] for item in payload["target_levels"]] == ["beginner", "intermediate", "challenge"]
    # v2.2: focus_topics_recommended 至少 8 项
    assert len(payload["focus_topics_recommended"]) >= 8
