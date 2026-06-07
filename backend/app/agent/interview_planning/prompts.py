"""Planning Prompt：拼装首次生成与重新生成时发给 LLM 的 system/user prompt。"""
from __future__ import annotations

from typing import Any

from app.services.interview_configuration_service import INTERVIEW_TYPES, LANGUAGES, TARGET_LEVELS, TARGET_ROLES
from app.services.interview_planning.constants import REGENERATION_STRATEGY_LABELS, REGENERATION_STRATEGY_LLM_INSTRUCTIONS


def build_planning_prompt(
    *,
    configuration: dict[str, Any],
    resume: dict[str, Any],
    role_knowledge_context: str = "",
    validation_feedback: str = "",
    previous_plan_summary: dict[str, Any] | None = None,
    regeneration_feedback: dict[str, Any] | None = None,
) -> tuple[str, str]:
    labels = _configuration_labels(configuration)
    interview_type = configuration["interview_type"]
    has_jd = bool(str(configuration.get("jd_text", "")).strip())
    type_label = labels["interview_type_label"]
    role_label = labels["target_role_label"]
    language_label = labels["language_label"]
    level_label = labels["target_level_label"]
    focus_topics = configuration.get("focus_topics", [])
    jd_text = str(configuration.get("jd_text", "")).strip()

    if interview_type == "campus":
        dimension_block = _campus_dimension_block()
        audience_hint = "候选人面向校招/应届，重点考察基础、项目/实习、问题分析能力与成长潜力。"
    else:
        dimension_block = _experienced_dimension_block()
        audience_hint = "候选人面向社招，重点考察项目贡献、技术深度、系统设计、故障处理或业务理解。"

    jd_block = (
        f"已提供 JD，需优先对齐以下岗位要求（仅作参考，不要逐句复述）：\n{jd_text[:1200]}"
        if has_jd
        else "未提供 JD，请按目标岗位通用模式组织计划，不要编造 JD 要求。"
    )

    feedback_block = f"\n上次输出未通过校验，请修正以下问题后重新生成：\n{validation_feedback}\n" if validation_feedback else ""
    regeneration_block = _build_regeneration_block(
        previous_plan_summary=previous_plan_summary,
        regeneration_feedback=regeneration_feedback,
    )

    system_prompt = (
        "你是面试计划 Planning Agent，只能返回 JSON。"
        "你必须在内部完成简历/JD 匹配分析，但 candidate_summary 只能输出短句摘要，"
        "不得输出完整开场题、追问话术或评分细则。"
    )

    prompt = f"""
请基于以下输入生成 45 分钟面试计划（4 至 5 个考察主题）。

## 面试配置
- 面试类型: {type_label}
- 目标岗位: {role_label}
- 技术语言: {language_label}
- 目标难度: {level_label}
- 用户选择的重点方向: {focus_topics}
- 时长: 45 分钟（主题 estimated_minutes 总和不超过 40，预留 5 分钟收尾）

## 候选人类型
{audience_hint}

## JD 信息
{jd_block}

## 必须覆盖维度
{dimension_block}

## 简历摘要
- 个人信息: {resume.get("personal_info", "")}
- 亮点: {resume.get("highlights", [])}
- 技能: {resume.get("technical_skills", [])}
- 工作经历: {_format_entries(resume.get("work_experience", []))}
- 项目经历: {_format_entries(resume.get("project_experience", []))}

## 岗位知识（可为空）
{role_knowledge_context or "暂无额外岗位知识，请结合配置与简历生成。"}

{feedback_block}
{regeneration_block}

## 输出要求
1. 优先生成 5 个主题；简历/JD 信息较少时可 4 个；禁止生成 6 个及以上。
2. 至少 4 个 required=true；若仅 4 个主题则必须全部为 required=true。
3. 每个主题必须包含完整 metadata（opening_question 仅内部使用，摘要中不得复述）。
4. reference_summary 输出 1 至 3 条短句，说明会重点参考哪些简历/JD 要点；{'有 JD 时必须体现 JD 关键词。' if has_jd else '无 JD 时说明按岗位通用模式。'}
5. 主题名称应贴合 {role_label} 与 {language_label}，不要照搬示例。
6. 只返回 JSON，格式如下：
{{
  "topics": [
    {{
      "id": "topic-1",
      "name": "主题名",
      "dimension": "对应必须维度之一",
      "objective": "验证目标",
      "focus_points": ["考察点1", "考察点2"],
      "required": true,
      "estimated_minutes": 8,
      "max_rounds": 3,
      "opening_question": "内部开场题，不在摘要展示",
      "expected_signals": ["信号1", "信号2"],
      "probe_strategies": ["追问策略1"],
      "evaluation_criteria": "评分要点",
      "source_refs": ["resume:project_x", "jd:optional"]
    }}
  ],
  "candidate_summary": {{
    "focus_topics": {focus_topics},
    "reference_summary": ["短摘要1", "短摘要2"]
  }}
}}
"""
    return prompt.strip(), system_prompt


def _build_regeneration_block(
    *,
    previous_plan_summary: dict[str, Any] | None,
    regeneration_feedback: dict[str, Any] | None,
) -> str:
    if not regeneration_feedback:
        return ""

    strategy = regeneration_feedback.get("regeneration_strategy", "")
    strategy_label = REGENERATION_STRATEGY_LABELS.get(strategy, strategy)
    additional_instruction = str(regeneration_feedback.get("additional_instruction", "") or "").strip()
    instructions = REGENERATION_STRATEGY_LLM_INSTRUCTIONS.get(strategy, [])

    lines = [
        "## 重新生成反馈",
        f"- 调整策略: {strategy_label} ({strategy})",
        "- 本次为重新生成，新计划必须与上一版存在实质差异，不可原样复用。",
    ]
    if instructions:
        lines.append("- 本策略必须遵守：")
        lines.extend(f"  - {item}" for item in instructions)
    if strategy == "different_plan" and additional_instruction:
        lines.append(f"- 用户补充说明（换套首要意图）: {additional_instruction}")
    if previous_plan_summary:
        lines.append("- 上一版计划摘要（供对比，须产生有效差异）:")
        lines.append(f"  - 版本: {previous_plan_summary.get('version')}")
        lines.append(f"  - 参考摘要: {previous_plan_summary.get('reference_summary', [])}")
        lines.append(f"  - focus_topics: {previous_plan_summary.get('focus_topics', [])}")
        for topic in previous_plan_summary.get("topics", []):
            if not isinstance(topic, dict):
                continue
            name = topic.get("name", "")
            dimension = topic.get("dimension", "")
            required = topic.get("required", False)
            minutes = topic.get("estimated_minutes", "")
            focus_points = topic.get("focus_points", [])
            lines.append(
                f"  - 主题: {name} | dimension={dimension} | required={required} | "
                f"minutes={minutes} | focus_points={focus_points}"
            )
    return "\n".join(lines)


def _experienced_dimension_block() -> str:
    return "\n".join(
        [
            "- 项目所有权和个人贡献",
            "- 技术深度",
            "- 方案取舍或系统设计",
            "- 故障处理、工程质量或业务理解（至少覆盖其中一项）",
        ]
    )


def _campus_dimension_block() -> str:
    return "\n".join(
        [
            "- 技术或专业基础",
            "- 项目、实习或竞赛经历",
            "- 问题分析能力",
            "- 学习能力或成长潜力",
        ]
    )


def _format_entries(entries: Any) -> str:
    if not isinstance(entries, list) or not entries:
        return "暂无"
    lines: list[str] = []
    for item in entries[:4]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("title") or "未命名").strip()
        detail = str(item.get("detail") or item.get("description") or "").strip()
        lines.append(f"- {name}: {detail[:160]}")
    return "\n".join(lines) or "暂无"


def _configuration_labels(configuration: dict[str, Any]) -> dict[str, str]:
    lookup = {
        "interview_type": {item["value"]: item["label"] for item in INTERVIEW_TYPES},
        "target_role": {item["value"]: item["label"] for item in TARGET_ROLES},
        "language": {item["value"]: item["label"] for item in LANGUAGES},
        "target_level": {item["value"]: item["label"] for item in TARGET_LEVELS},
    }
    result: dict[str, str] = {}
    for field in ("interview_type", "target_role", "language", "target_level"):
        value = configuration[field]
        result[field] = value
        result[f"{field}_label"] = lookup[field].get(value, value)
    return result
