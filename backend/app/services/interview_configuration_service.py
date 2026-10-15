from typing import Any


DURATION_MINUTES = 45
MAX_FOCUS_TOPICS = 6

# v1.1: 维护一份「中英文双语」枚举。后端透传给前端，前端按 UI locale 选 label。
INTERVIEW_TYPES: list[dict[str, str]] = [
    {"value": "campus", "label_en": "Campus", "label_zh": "校招"},
    {"value": "experienced", "label_en": "Experienced", "label_zh": "社招"},
]

TARGET_ROLES: list[dict[str, str]] = [
    {"value": "frontend", "label_en": "Frontend", "label_zh": "前端开发"},
    {"value": "backend", "label_en": "Backend", "label_zh": "后端开发"},
    {"value": "fullstack", "label_en": "Full-stack", "label_zh": "全栈开发"},
    {"value": "agent", "label_en": "Agent", "label_zh": "Agent 开发"},
]

LANGUAGES: list[dict[str, str]] = [
    {"value": "java", "label_en": "Java", "label_zh": "Java"},
    {"value": "python", "label_en": "Python", "label_zh": "Python"},
    {"value": "go", "label_en": "Go", "label_zh": "Go"},
    {"value": "javascript", "label_en": "JavaScript", "label_zh": "JavaScript"},
]

TARGET_LEVELS: list[dict[str, str]] = [
    {"value": "beginner", "label_en": "Beginner", "label_zh": "入门"},
    {"value": "intermediate", "label_en": "Intermediate", "label_zh": "进阶"},
    {"value": "challenge", "label_en": "Advanced", "label_zh": "挑战"},
]

_LABEL_FIELDS: tuple[str, ...] = ("interview_type", "target_role", "language", "target_level")
_ENUM_BY_FIELD: dict[str, list[dict[str, str]]] = {
    "interview_type": INTERVIEW_TYPES,
    "target_role": TARGET_ROLES,
    "language": LANGUAGES,
    "target_level": TARGET_LEVELS,
}
# Plural keys for get_options() response (kept for API compatibility)
_OPTIONS_KEY_BY_FIELD: dict[str, str] = {
    "interview_type": "interview_types",
    "target_role": "target_roles",
    "language": "languages",
    "target_level": "target_levels",
}


def _label_for(item: dict[str, str], locale: str) -> str:
    return item["label_en"] if locale == "en" else item["label_zh"]


def configuration_labels(configuration: dict[str, Any], *, locale: str = "zh") -> dict[str, str]:
    """v1.0 兼容：根据 locale 选 zh/en 标签。"""
    result: dict[str, str] = {}
    for field in _LABEL_FIELDS:
        value = str(configuration.get(field, "")).strip()
        result[field] = value
        lookup = {item["value"]: _label_for(item, locale) for item in _ENUM_BY_FIELD[field]}
        result[f"{field}_label"] = lookup.get(value, value)
    return result


class InterviewConfigurationService:
    def get_options(self, locale: str = "en") -> dict[str, Any]:
        """v1.1: 返回双语 options；label 字段按 locale 给出（兼容 v1.0）。"""
        return {
            _OPTIONS_KEY_BY_FIELD[field]: [
                {"value": item["value"], "label": _label_for(item, locale)}
                for item in _ENUM_BY_FIELD[field]
            ]
            for field in _LABEL_FIELDS
        } | {
            "duration_minutes": DURATION_MINUTES,
            "max_focus_topics": MAX_FOCUS_TOPICS,
        }


