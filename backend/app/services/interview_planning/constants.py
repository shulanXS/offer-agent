"""Planning 常量：计划边界、重新生成策略枚举及 LLM 策略说明。"""
PLAN_BOUNDARIES = {
    "duration_minutes": 45,
    "max_answer_rounds": 12,
    "max_probes_per_topic": 2,
    "closing_buffer_minutes": 5,
}

MAX_REGENERATIONS = 2
MAX_JD_TEXT_LENGTH = 8000
MIN_RESUME_TEXT_LENGTH = 20
MAX_ADDITIONAL_INSTRUCTION_LENGTH = 200

REGENERATION_STRATEGIES = (
    "align_resume",
    "align_jd",
    "increase_technical_depth",
    "increase_fundamentals",
    "increase_practical_cases",
    "different_plan",
)

REGENERATION_STRATEGY_LABELS: dict[str, str] = {
    "align_resume": "更贴合简历",
    "align_jd": "更贴合目标 JD",
    "increase_technical_depth": "加强技术深度",
    "increase_fundamentals": "加强基础考察",
    "increase_practical_cases": "加强实战案例",
    "different_plan": "换一套计划",
}

REGENERATION_STRATEGY_LLM_INSTRUCTIONS: dict[str, list[str]] = {
    "align_resume": [
        "至少 2 个主题的 source_refs 指向简历中的具体项目、公司或技能（如 resume:项目名）。",
        "reference_summary 中至少 1 条须点名简历中的项目、技能或经历要点。",
        "opening_question 与 focus_points 须围绕候选人真实经历展开，避免空泛套话。",
    ],
    "align_jd": [
        "至少 2 个主题的 dimension 或 focus_points 须对齐 JD 中的岗位要求关键词。",
        "reference_summary 中至少 1 条须体现 JD 关键要求（不要逐句复述 JD 原文）。",
        "至少 1 个主题的 source_refs 使用 jd: 前缀引用 JD 要点。",
    ],
    "increase_technical_depth": [
        "至少 2 个主题强化实现细节、原理、架构取舍或技术难点类 focus_points。",
        "优先加深「技术深度」「系统设计」等相关 dimension 的主题权重（required 或 estimated_minutes）。",
        "opening_question 应能引出深度追问，而非仅停留在概念层面。",
    ],
    "increase_fundamentals": [
        "至少 2 个主题偏向语言机制、数据结构、基础原理、核心概念或专业基础。",
        "校招计划应更明显体现基础与原理考察；社招也须至少 1 个主题侧重基础巩固。",
        "focus_points 中避免只谈业务叙事，须包含可验证的基础知识点。",
    ],
    "increase_practical_cases": [
        "至少 2 个主题强调故障排查、线上问题、项目 trade-off、实战案例或工程落地。",
        "focus_points 须包含可追问的具体场景（如性能、稳定性、排查路径）。",
        "reference_summary 须体现将结合实战/项目案例组织考察。",
    ],
    "different_plan": [
        "与上一版相比，至少 3 个主题 name 须不同。",
        "若 name 变化不足 3 个，则至少 2 个 name 不同且 2 个 dimension 组合发生变化。",
        "不得仅修改 reference_summary 措辞而保持主题结构与 focus_points 基本不变。",
        "若用户提供补充说明，须将其作为本次换套的首要意图，体现在主题排列、名称与 focus_points 中。",
    ],
}
