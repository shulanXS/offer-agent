from typing import Any


DURATION_MINUTES_OPTIONS: list[int] = [15, 30, 45, 60]
ALLOWED_DURATIONS: tuple[int, ...] = tuple(DURATION_MINUTES_OPTIONS)
DEFAULT_DURATION_MINUTES = 45
MAX_FOCUS_TOPICS = 8  # v2.2：从 6 提到 8，支持 custom 输入

# v2.2: 维护一份「中英文双语」枚举。后端透传给前端，前端按 UI locale 选 label。
INTERVIEW_TYPES: list[dict[str, str]] = [
    {"value": "intern", "label_en": "Intern", "label_zh": "实习"},
    {"value": "campus", "label_en": "Campus", "label_zh": "校招"},
    {"value": "experienced", "label_en": "Experienced", "label_zh": "社招"},
]

TARGET_ROLES: list[dict[str, str]] = [
    {"value": "frontend", "label_en": "Frontend", "label_zh": "前端开发"},
    {"value": "backend", "label_en": "Backend", "label_zh": "后端开发"},
    {"value": "fullstack", "label_en": "Full-stack", "label_zh": "全栈开发"},
    {"value": "agent", "label_en": "Agent", "label_zh": "Agent 开发"},
    {"value": "data_ml", "label_en": "Data / ML", "label_zh": "数据 / 算法"},
    {"value": "mobile", "label_en": "Mobile (iOS/Android)", "label_zh": "移动端 (iOS/Android)"},
    {"value": "qa", "label_en": "QA / Test", "label_zh": "测试 / QA"},
    {"value": "sre", "label_en": "SRE / DevOps", "label_zh": "SRE / DevOps"},
    {"value": "embedded", "label_en": "Embedded", "label_zh": "嵌入式"},
    {"value": "__custom__", "label_en": "Custom…", "label_zh": "自定义…"},
]

# v2.2: 删掉 LANGUAGES 下发（前端 UI 不再展示）。保留兼容常量供老 session 反序列化。
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

# v2.2: 常用 focus topics 14 个 + 用户可自定义输入。
FOCUS_TOPICS_RECOMMENDED: list[dict[str, str]] = [
    {"value": "项目深挖", "label_en": "Project Deep Dive", "label_zh": "项目深挖"},
    {"value": "技术基础", "label_en": "Tech Fundamentals", "label_zh": "技术基础"},
    {"value": "系统设计", "label_en": "System Design", "label_zh": "系统设计"},
    {"value": "业务理解", "label_en": "Business Sense", "label_zh": "业务理解"},
    {"value": "问题排查", "label_en": "Troubleshooting", "label_zh": "问题排查"},
    {"value": "沟通表达", "label_en": "Communication", "label_zh": "沟通表达"},
    {"value": "算法与编码", "label_en": "Algorithms & Coding", "label_zh": "算法与编码"},
    {"value": "数据结构", "label_en": "Data Structures", "label_zh": "数据结构"},
    {"value": "SQL与数据库", "label_en": "SQL & Database", "label_zh": "SQL 与数据库"},
    {"value": "并发与性能", "label_en": "Concurrency & Performance", "label_zh": "并发与性能"},
    {"value": "安全与可靠性", "label_en": "Security & Reliability", "label_zh": "安全与可靠性"},
    {"value": "ML模型理解", "label_en": "ML Concepts", "label_zh": "ML 模型理解"},
    {"value": "Agent工程能力", "label_en": "Agent Engineering", "label_zh": "Agent 工程能力"},
    {"value": "行业趋势", "label_en": "Industry Trends", "label_zh": "行业趋势"},
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
        """v2.2: 返回双语 options；label 字段按 locale 给出（兼容 v1.0）。
        - 新增 focus_topics_recommended 列表
        - 新增 duration_minutes_options 与 include_algorithm_supported 标志
        - languages 仍下发以便老前端兼容，但 UI 已不展示
        """
        return {
            _OPTIONS_KEY_BY_FIELD[field]: [
                {"value": item["value"], "label": _label_for(item, locale)}
                for item in _ENUM_BY_FIELD[field]
            ]
            for field in _LABEL_FIELDS
        } | {
            "duration_minutes": DEFAULT_DURATION_MINUTES,
            "duration_minutes_options": DURATION_MINUTES_OPTIONS,
            "include_algorithm_supported": True,
            "max_focus_topics": MAX_FOCUS_TOPICS,
            "focus_topics_recommended": [
                {"value": item["value"], "label": _label_for(item, locale)}
                for item in FOCUS_TOPICS_RECOMMENDED
            ],
        }


