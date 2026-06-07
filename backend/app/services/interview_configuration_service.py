from typing import Any


DURATION_MINUTES = 45
MAX_FOCUS_TOPICS = 6

INTERVIEW_TYPES = [
    {"value": "campus", "label": "校招"},
    {"value": "experienced", "label": "社招"},
]

TARGET_ROLES = [
    {"value": "frontend", "label": "前端开发"},
    {"value": "backend", "label": "后端开发"},
    {"value": "fullstack", "label": "全栈开发"},
    {"value": "agent", "label": "Agent 开发"},
]

LANGUAGES = [
    {"value": "java", "label": "Java"},
    {"value": "python", "label": "Python"},
    {"value": "go", "label": "Go"},
    {"value": "javascript", "label": "JavaScript"},
]

TARGET_LEVELS = [
    {"value": "beginner", "label": "入门"},
    {"value": "intermediate", "label": "进阶"},
    {"value": "challenge", "label": "挑战"},
]

_LABEL_LOOKUP = {
    "interview_type": {item["value"]: item["label"] for item in INTERVIEW_TYPES},
    "target_role": {item["value"]: item["label"] for item in TARGET_ROLES},
    "language": {item["value"]: item["label"] for item in LANGUAGES},
    "target_level": {item["value"]: item["label"] for item in TARGET_LEVELS},
}


def configuration_labels(configuration: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for field in ("interview_type", "target_role", "language", "target_level"):
        value = str(configuration.get(field, "")).strip()
        result[field] = value
        result[f"{field}_label"] = _LABEL_LOOKUP[field].get(value, value)
    return result


class InterviewConfigurationService:
    def get_options(self) -> dict[str, Any]:
        return {
            "interview_types": INTERVIEW_TYPES,
            "target_roles": TARGET_ROLES,
            "languages": LANGUAGES,
            "target_levels": TARGET_LEVELS,
            "duration_minutes": DURATION_MINUTES,
            "max_focus_topics": MAX_FOCUS_TOPICS,
        }
