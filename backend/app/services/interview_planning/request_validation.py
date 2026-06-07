"""Planning 请求校验：校验创建面试与重新生成 API 的入参（配置、策略、JD、补充说明等）。"""
from typing import Any

from app.core.errors import ErrorCode, raise_app_error
from app.services.interview_configuration_service import DURATION_MINUTES, INTERVIEW_TYPES, LANGUAGES, MAX_FOCUS_TOPICS, TARGET_LEVELS, TARGET_ROLES
from app.services.interview_planning.constants import (
    MAX_ADDITIONAL_INSTRUCTION_LENGTH,
    MAX_JD_TEXT_LENGTH,
    MIN_RESUME_TEXT_LENGTH,
    REGENERATION_STRATEGIES,
)

_ALLOWED_CONFIGURATION = {
    "interview_type": {item["value"] for item in INTERVIEW_TYPES},
    "target_role": {item["value"] for item in TARGET_ROLES},
    "language": {item["value"] for item in LANGUAGES},
    "target_level": {item["value"] for item in TARGET_LEVELS},
}


def validate_interview_configuration(payload: dict[str, Any], *, trace_id: str = "") -> dict[str, Any]:
    resume_id = str(payload.get("resume_id", "")).strip()
    if not resume_id:
        raise_app_error(400, ErrorCode.INTERVIEW_CONFIG_INVALID, "请选择简历", trace_id=trace_id)

    for field, allowed in _ALLOWED_CONFIGURATION.items():
        value = str(payload.get(field, "")).strip()
        if value not in allowed:
            raise_app_error(
                400,
                ErrorCode.INTERVIEW_CONFIG_INVALID,
                f"字段 {field} 不在允许范围内",
                trace_id=trace_id,
                details={"field": field, "value": value},
            )

    duration_minutes = payload.get("duration_minutes", DURATION_MINUTES)
    if duration_minutes != DURATION_MINUTES:
        raise_app_error(
            400,
            ErrorCode.INTERVIEW_CONFIG_INVALID,
            f"面试时长固定为 {DURATION_MINUTES} 分钟",
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

    return {
        "resume_id": resume_id,
        "interview_type": str(payload["interview_type"]).strip(),
        "target_role": str(payload["target_role"]).strip(),
        "language": str(payload["language"]).strip(),
        "target_level": str(payload["target_level"]).strip(),
        "duration_minutes": DURATION_MINUTES,
        "focus_topics": focus_topics,
        "jd_text": jd_text.strip(),
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
