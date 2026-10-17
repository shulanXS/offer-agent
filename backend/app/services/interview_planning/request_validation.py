"""Planning 请求校验：校验创建面试与重新生成 API 的入参（配置、策略、JD、补充说明等）。"""
from typing import Any

from app.core.errors import ErrorCode, raise_app_error
from app.services.interview_configuration_service import (
    ALLOWED_DURATIONS,
    DEFAULT_DURATION_MINUTES,
    INTERVIEW_TYPES,
    LANGUAGES,
    MAX_FOCUS_TOPICS,
    TARGET_LEVELS,
    TARGET_ROLES,
)
from app.services.interview_planning.constants import (
    MAX_ADDITIONAL_INSTRUCTION_LENGTH,
    MAX_JD_TEXT_LENGTH,
    MIN_RESUME_TEXT_LENGTH,
    REGENERATION_STRATEGIES,
)

# v2.2: 允许的 target_role 值集合。`__custom__` 走 custom_target_role 字段
# 验证，因此从白名单中排除（自定义值通过后续 normalize 步骤注入）。
_ALLOWED_CONFIGURATION = {
    "interview_type": {item["value"] for item in INTERVIEW_TYPES},
    "target_role": {item["value"] for item in TARGET_ROLES} - {"__custom__"},
    "language": {item["value"] for item in LANGUAGES},
    "target_level": {item["value"] for item in TARGET_LEVELS},
}

# v2.3: 面试语言白名单（en/zh）。C1 配置漂移根因。
ALLOWED_INTERVIEW_LANGUAGES = {"en", "zh"}
DEFAULT_INTERVIEW_LANGUAGE = "en"


def validate_interview_configuration(payload: dict[str, Any], *, trace_id: str = "") -> dict[str, Any]:
    resume_id = str(payload.get("resume_id", "")).strip()
    if not resume_id:
        raise_app_error(400, ErrorCode.INTERVIEW_CONFIG_INVALID, "请选择简历", trace_id=trace_id)

    interview_type = str(payload.get("interview_type", "")).strip()
    if interview_type not in _ALLOWED_CONFIGURATION["interview_type"]:
        raise_app_error(
            400,
            ErrorCode.INTERVIEW_CONFIG_INVALID,
            "字段 interview_type 不在允许范围内",
            trace_id=trace_id,
            details={"field": "interview_type", "value": interview_type},
        )

    target_role_raw = str(payload.get("target_role", "")).strip()
    custom_target_role = str(payload.get("custom_target_role", "")).strip()
    if target_role_raw == "__custom__":
        if not custom_target_role:
            raise_app_error(
                400,
                ErrorCode.INTERVIEW_CONFIG_INVALID,
                "请填写自定义 target role",
                trace_id=trace_id,
            )
        target_role = custom_target_role
    elif target_role_raw in _ALLOWED_CONFIGURATION["target_role"]:
        target_role = target_role_raw
    else:
        raise_app_error(
            400,
            ErrorCode.INTERVIEW_CONFIG_INVALID,
            "字段 target_role 不在允许范围内",
            trace_id=trace_id,
            details={"field": "target_role", "value": target_role_raw},
        )

    target_level = str(payload.get("target_level", "")).strip()
    if target_level not in _ALLOWED_CONFIGURATION["target_level"]:
        raise_app_error(
            400,
            ErrorCode.INTERVIEW_CONFIG_INVALID,
            "字段 target_level 不在允许范围内",
            trace_id=trace_id,
            details={"field": "target_level", "value": target_level},
        )

    # v2.2: 兼容旧字段 language，缺省视为空字符串
    language = str(payload.get("language", "")).strip() or "any"

    # v2.3: interview_language 是新权威字段；白名单 {en, zh}，默认 en。
    interview_language_raw = str(payload.get("interview_language", "")).strip().lower()
    if not interview_language_raw:
        interview_language = DEFAULT_INTERVIEW_LANGUAGE
    elif interview_language_raw in ALLOWED_INTERVIEW_LANGUAGES:
        interview_language = interview_language_raw
    else:
        raise_app_error(
            400,
            ErrorCode.INTERVIEW_LANGUAGE_INVALID,
            f"interview_language 必须是 {sorted(ALLOWED_INTERVIEW_LANGUAGES)} 中的一个",
            trace_id=trace_id,
            details={"field": "interview_language", "value": interview_language_raw},
        )

    duration_minutes = int(payload.get("duration_minutes", DEFAULT_DURATION_MINUTES) or DEFAULT_DURATION_MINUTES)
    if duration_minutes not in ALLOWED_DURATIONS:
        raise_app_error(
            400,
            ErrorCode.INTERVIEW_CONFIG_INVALID,
            f"面试时长必须是 {ALLOWED_DURATIONS} 中的一个",
            trace_id=trace_id,
        )

    focus_topics = normalize_focus_topics(payload.get("focus_topics", []))
    if not focus_topics:
        raise_app_error(400, ErrorCode.INTERVIEW_CONFIG_INVALID, "请至少选择一个重点方向", trace_id=trace_id)
    if len(focus_topics) > MAX_FOCUS_TOPICS:
        raise_app_error(
            400,
            ErrorCode.INTERVIEW_CONFIG_INVALID,
            f"重点方向最多 {MAX_FOCUS_TOPICS} 个",
            trace_id=trace_id,
        )

    jd_text = str(payload.get("jd_text", "") or "")
    if len(jd_text) > MAX_JD_TEXT_LENGTH:
        raise_app_error(
            400,
            ErrorCode.INTERVIEW_CONFIG_INVALID,
            f"JD 文本不能超过 {MAX_JD_TEXT_LENGTH} 字",
            trace_id=trace_id,
        )

    # v2.2: 开启算法轮次的合法性
    include_algorithm = bool(payload.get("include_algorithm", False))
    if include_algorithm and interview_type == "experienced":
        # experienced 默认不开，但允许手动开启；不强约束
        pass

    return {
        "resume_id": resume_id,
        "interview_type": interview_type,
        "target_role": target_role,
        "language": language,
        "interview_language": interview_language,
        "target_level": target_level,
        "duration_minutes": duration_minutes,
        "focus_topics": focus_topics,
        "jd_text": jd_text.strip(),
        "include_algorithm": include_algorithm,
    }


def validate_resume_for_planning(resume: dict[str, Any] | None, *, trace_id: str = "") -> dict[str, Any]:
    if not resume:
        raise_app_error(404, ErrorCode.RESUME_NOT_FOUND, "简历不存在", trace_id=trace_id)

    resume_text = str(resume.get("resume_text", "") or "").strip()
    if len(resume_text) < MIN_RESUME_TEXT_LENGTH:
        raise_app_error(
            400,
            ErrorCode.INTERVIEW_CONFIG_INVALID,
            "请先上传并解析简历，或确保简历内容足够完整",
            trace_id=trace_id,
        )
    return resume


def validate_regeneration_request(payload: dict[str, Any], *, configuration: dict[str, Any], trace_id: str = "") -> dict[str, Any]:
    strategy = str(payload.get("regeneration_strategy", "")).strip()
    if strategy not in REGENERATION_STRATEGIES:
        raise_app_error(
            400,
            ErrorCode.INTERVIEW_CONFIG_INVALID,
            "请选择有效的调整策略",
            trace_id=trace_id,
            details={"field": "regeneration_strategy", "value": strategy},
        )

    has_jd = bool(str(configuration.get("jd_text", "")).strip())
    if strategy == "align_jd" and not has_jd:
        raise_app_error(400, ErrorCode.INTERVIEW_CONFIG_INVALID, "未提供 JD 时不能选择「更贴合目标 JD」", trace_id=trace_id)

    additional_instruction = str(payload.get("additional_instruction", "") or "").strip()
    if additional_instruction and strategy != "different_plan":
        raise_app_error(
            400,
            ErrorCode.INTERVIEW_CONFIG_INVALID,
            "仅「换一套计划」策略支持补充说明",
            trace_id=trace_id,
        )
    if len(additional_instruction) > MAX_ADDITIONAL_INSTRUCTION_LENGTH:
        raise_app_error(
            400,
            ErrorCode.INTERVIEW_CONFIG_INVALID,
            f"补充说明不能超过 {MAX_ADDITIONAL_INSTRUCTION_LENGTH} 字",
            trace_id=trace_id,
        )

    return {
        "regeneration_strategy": strategy,
        "additional_instruction": additional_instruction,
    }


def normalize_focus_topics(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    topics: list[str] = []
    for item in raw:
        text = str(item).strip()
        if text and text not in topics:
            topics.append(text)
    return topics
