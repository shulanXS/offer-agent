from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_interview_options_returns_fixed_enums() -> None:
    response = client.get("/api/interview-options")

    assert response.status_code == 200
    payload = response.json()
    assert payload["duration_minutes"] == 45
    assert payload["max_focus_topics"] == 6
    assert payload["interview_types"] == [
        {"value": "campus", "label": "校招"},
        {"value": "experienced", "label": "社招"},
    ]
    assert [item["value"] for item in payload["target_roles"]] == ["frontend", "backend", "fullstack", "agent"]
    assert [item["value"] for item in payload["languages"]] == ["java", "python", "go", "javascript"]
    assert [item["value"] for item in payload["target_levels"]] == ["beginner", "intermediate", "challenge"]
