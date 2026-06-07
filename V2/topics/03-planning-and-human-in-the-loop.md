# 面试计划与人工介入

## 1. 文档状态

- 状态：**已完成**（小步 1–5 + 收尾优化）
- 对应路线图：阶段 4、阶段 5
- 核心 Agent：Planning Agent
- 前置专题：02 面试配置与 JD

### 1.1 产品拍板（已确认）

| 项 | 决定 |
|---|---|
| 配置校验 | 全部由本专题在 `POST /api/interviews` 完成；02 不做校验 API |
| 摘要边界 | 候选人摘要**绝不展示**完整开场题、追问话术、评分锚点 |
| niumian | **选择性借鉴**（维度 + 校验 + JD 分支）；不照搬 8 题清单与简历优化 Prompt |
| 模板降级 | **小步 2 必做**（LLM/校验失败后的本地岗位模板兜底） |
| 按钮接口 | 配置页「生成面试计划」→ `POST /api/interviews`，**服务端内含首次 generate** |
| 独立 generate | `POST .../plan/generate` 与 `.../plan/regenerate` **均保留**（重试 / 预览页 regenerate） |

## 2. 改造目标

根据配置页提交的一次性面试配置草稿、基础简历解析结果和可选 JD 文本，生成一份有明确边界的 45 分钟**面试计划**。候选人可以查看计划摘要、选择调整策略重新生成、**最多额外重新生成 2 次**，并在开始前确认锁定。

本专题**对用户交付计划摘要**，不对用户交付完整题目清单；计划内部的考察抓手由 Planning Agent 生成，供专题 04 动态面试消费。

## 3. 本专题范围

### 负责

- 接收专题 02 配置草稿并完成服务端校验
- 创建新版面试会话和计划
- Planning Agent（含计划内部分析，不单独产出用户可见简历分析报告）
- 计划规则校验、有限重试和模板降级（小步 2 起）
- 候选人可见计划摘要
- 重新生成策略、最多额外重新生成 2 次、确认锁定
- 本专题涉及的页面、数据、状态、API、测试和日志

**本专题 03 阶段不做：**

### 不负责

- 独立配置表或 `configuration_id`（已在 02 明确取消）
- JD 结构化解析（仅消费 `jd_text` 原文）
- 用户可见的简历优化/简历深度分析报告
- 一次性生成完整题目清单并展示给候选人（niumian 简历面试模式）
- 开始正式面试、动态追问、证据提取、最终评分
## 4. 依赖契约

### 4.1 消费专题 02

- 用户在配置页点击「生成面试计划」时，前端将 §4.2 配置草稿随 `POST /api/interviews` 一次性提交。
- 本专题负责校验：`resume_id` 归属、枚举合法、`focus_topics` 数量、JD 长度、固定 45 分钟等。
- 消费基础简历解析结果（`personal_info`、`work_experience`、`project_experience`、`technical_skills`、`resume_text` 等），**不依赖** 02 的配置持久化或独立校验 API。
- JD 仅消费 `jd_text` 原文；无 JD 时使用岗位通用模式。

### 4.2 配置草稿 Schema（来自 02）

```json
{
  "resume_id": "resume-id",
  "interview_type": "experienced",
  "target_role": "backend",
  "language": "java",
  "target_level": "intermediate",
  "duration_minutes": 45,
  "focus_topics": ["系统设计", "项目深挖"],
  "jd_text": ""
}
```

### 4.3 向专题 04 输出

- 已锁定、不可变的 `plan_json` 与 `candidate_summary_json`。
- 专题 04 只消费 `plan_confirmed` 后的计划，不读取配置页临时状态。

### 4.4 岗位知识边界（V2 不改造 RAG）

- V2 **不接入** Planning / Interview / Evaluation 分阶段 RAG；`get_planning_context()` 返回空 context，不调用 `PlanningRAGService`。
- **模板降级**（小步 2）指 LLM/校验全失败时的本地岗位计划骨架；V2 主路径为 LLM + 模板降级。

### 4.5 旧能力处理边界

- 直接保留：LLM Factory、模型配置、结构化输出与日志工具。
- 允许借鉴：niumian 简历面试 Prompt 中的**考察维度、有/无 JD 分支、代码校验与重试**；见 §5.5（**选择性借鉴**，非深度照搬）。
- 禁止照搬：niumian 的完整题目清单产品形态、`GENERATE_CALCULATE_CV_QUESTION_LIST_V2` 原样复用、押题/简历优化/简历解析链路。
- 替换重构：Planning Agent、计划 Schema、确定性边界校验、版本管理、重新生成、确认锁定、新版会话和计划数据。
- 允许破坏：旧 `CvInterviewWorkflow` 出题节点、固定四题结构、旧 `InterviewService` 启动即出题流程。

## 5. 产品规则

### 5.1 计划固定边界

| 项目 | 规则 |
|---|---:|
| 时长 | 45 分钟 |
| 主题数 | 4 至 5 个（优先生成 5 个；不接受 6 个） |
| 必须主题 | 至少 4 个 |
| 单主题最大回答轮数 | 3 |
| 单主题最大追问数 | 2 |
| 整场最大回答轮数 | 12 |
| 收尾预留 | 5 分钟 |

### 5.2 计划 vs 题目清单（产品原则）

| 对用户 | 对系统（内部 `plan_json`） |
|---|---|
| 4–5 个考察方向、是否必考、约时、参考摘要 | 每主题含 objective、expected_signals、probe_strategies、opening_question |
| 不展示完整开场题、追问话术、参考答案 | 可借鉴 niumian 单题 metadata 粒度，但不生成固定 `question_list` |
| 可预览、regenerate、confirm | 锁定后供 04 按主题动态决策，而非按题号脚本 |

### 5.3 计划内容与摘要

**内部计划每个主题建议包含：**

- `id`、`name`、`objective`
- `dimension`（考察维度，见 §5.5）
- `focus_points`（具体考察点，类似 niumian 的 `focus_tech`）
- `required`、`estimated_minutes`、`max_rounds`
- `opening_question`（仅内部，摘要不可泄露）
- `expected_signals`、`probe_strategies`
- `evaluation_criteria`（评分要点，仅内部）
- `source_refs`（简历/JD 来源说明）

**候选人计划摘要只展示：**

- 面试配置摘要（岗位、语言、难度、校招/社招）
- 4–5 个考察方向名称与是否必考
- 重点参考的简历经历或 JD 要求摘要（短句，非分析报告）
- 预计 45 分钟
- 当前计划版本和剩余重新生成次数
- （可选）`generation_meta`：`source`、`generation_attempts`、`degraded`、`degraded_reason`

**不能展示：** 完整开场问题、具体追问、预期答案、评分锚点、内部风险点。

### 5.4 校招和社招必须覆盖

校招计划必须覆盖（至少映射到 1 个主题）：

- 技术或专业基础
- 项目、实习或竞赛经历
- 问题分析能力
- 学习能力或成长潜力

社招计划必须覆盖（至少映射到 1 个主题）：

- 项目所有权和个人贡献
- 技术深度
- 方案取舍或系统设计
- 故障处理、工程质量或业务理解中的至少一项

### 5.5 借鉴 niumian 简历面试的边界（选择性借鉴）

niumian 简历面试（`question_setter_agent_v2`, `type=cv`）**没有独立计划预览**，而是一次性生成 `question_list`。本专题**选择性借鉴**其计划生成内功，**不借鉴**其产品形态。

**首期必借：**

| niumian 做法 | 本专题映射 |
|---|---|
| 六大考察维度与社招维度配比思路 | 主题的 `dimension` + 必须覆盖校验 |
| Prompt 内五步：项目/JD 分析 → … → 一致性检查 | 小步 2 可**简化为 1–2 步**内部分析，不必完全复刻 |
| 每题 metadata：`dimension`、`focus_tech`、… | 收敛为**主题级** `focus_points`、`evaluation_criteria`（内部） |
| 有/无 JD 不同上下文组装 | `jd_text` 为空走通用岗位模式 |
| 生成后代码校验 + 有限重试 + 模型降级 | §6.4 确定性校验与降级 |
| 并行「简历分析」节点（与出题并行） | Planning 内部分析 resume/JD 匹配点，写入 `reference_summary`，**不是** niumian 的 AI 融合简历改写建议 |

**不应借鉴：**

| niumian 做法 | 原因 |
|---|---|
| 直接输出 8 道题 `question_list` 给用户或给对话 Agent | V2 04 需要主题级动态边界，不是固定题脚本 |
| `analysis_resume` 的 AI 融合/简历优化 Prompt | 与 02 取消「简历深度分析报告」一致 |
| 与简历押题共用同一出题 Prompt | 押题是题海产品；本专题是 45 分钟计划 |
| 创建后无预览、无 regenerate | V2 03 核心差异化 |

**社招维度参考（来自 niumian，映射为 Planning 内部分配比例，非硬性题数）：**

1. 技术基础与实践能力 — 主权重
2. 项目经历真实性验证
3. 系统架构设计思维
4. 专业领域深度洞察
5. 技术深度与前瞻视野
6. 团队协作与技术推动

Planning Agent 应把这些维度**收敛为 4–5 个主题**，而不是生成 8+ 道独立题目。

### 5.6 重新生成

- 首次计划版本为 1。
- **最多额外重新生成 2 次**（`MAX_REGENERATIONS = 2`），最终最多 **3 个计划版本**（v1 首次 + v2/v3 两次 regenerate）。
- 每次必须选择一个调整策略（共 **6 种**）。
- **仅「换一套计划」** 策略允许填写最多 200 字补充说明；其他策略若携带 `additional_instruction` 非空，后端返回 400。
- **重新生成不再接受 `focus_topics`**；考察重心以创建时的配置 `focus_topics` 为准，regenerate 只通过策略调整权重与组织方式。
- 有 JD 时才能选择「更贴合目标 JD」。
- 新计划必须与当前计划存在**有效差异**（比较主题 name、dimension、focus_points、opening_question 前缀及摘要等，非仅改文案）。
- 确认后锁定，不能继续重新生成。

**调整策略（当前实现）：**

```text
align_resume              # 更贴合简历
align_jd                  # 更贴合目标 JD（需 JD）
increase_technical_depth  # 加强技术深度
increase_fundamentals     # 加强基础考察
increase_practical_cases  # 加强实战案例
different_plan            # 换一套计划（唯一可填补充说明）
```

**策略如何生效：**

| 路径 | 行为 |
|---|---|
| LLM 主路径 | Prompt 注入 `REGENERATION_STRATEGY_LLM_INSTRUCTIONS`；校验通过后执行策略**后验**（`align_resume` / `align_jd` / `different_plan` 等）；失败触发 Agent 重试 |
| LLM 失败 / 模板降级 | `apply_regeneration_to_plan()` 做确定性微调；补充说明仅 `different_plan` 写入摘要 |

已移除策略：`adjust_topics`（与创建时 focus 及「加强 xxx」重叠，易混淆）。

## 6. Planning Agent 设计

### 6.1 输入

```json
{
  "configuration": {
    "resume_id": "resume-id",
    "interview_type": "experienced",
    "target_role": "backend",
    "language": "java",
    "target_level": "intermediate",
    "duration_minutes": 45,
    "focus_topics": ["系统设计", "项目深挖"],
    "jd_text": ""
  },
  "resume": {
    "personal_info": "",
    "work_experience": [],
    "project_experience": [],
    "technical_skills": [],
    "highlights": []
  },
  "role_knowledge_context": "",
  "planning_rag_sources": [],
  "previous_plan_summary": null,
  "regeneration_feedback": null
}
```

说明：

- `resume` 来自现有简历解析结果，不在本专题单独跑简历优化任务。
- `role_knowledge_context` 由 `get_planning_context()` 统一提供；**V2 恒返回空字符串**。
- 无 `structured_jd`；JD 只用 `configuration.jd_text`。

### 6.2 内部分析（不对用户单独展示）

Planning Agent 在生成主题前，应完成类似 niumian 的内部分析（可单 Prompt 多段，也可分步）：

1. 识别 2–3 个核心项目与技术栈覆盖
2. 对比 `focus_topics`、岗位、语言、难度与可选 JD 的匹配点
3. 选择组织策略：单项目深挖 / 业务链路串联 / 混合（仅影响主题排列，不暴露给用户）
4. 为校招或社招分配必须维度
5. 产出 `candidate_summary.reference_summary`（短摘要，非长篇报告）

### 6.3 输出

```json
{
  "duration_minutes": 45,
  "max_answer_rounds": 12,
  "max_probes_per_topic": 2,
  "closing_buffer_minutes": 5,
  "topics": [
    {
      "id": "topic-1",
      "name": "项目所有权",
      "dimension": "项目经历真实性验证",
      "objective": "验证候选人的真实职责和个人贡献",
      "focus_points": ["核心项目", "个人职责边界"],
      "required": true,
      "estimated_minutes": 8,
      "max_rounds": 3,
      "opening_question": "...",
      "expected_signals": ["职责边界", "个人贡献"],
      "probe_strategies": ["追问具体决策与结果"],
      "evaluation_criteria": "职责描述是否具体、可验证",
      "source_refs": ["resume:project_x", "jd:optional"]
    }
  ],
  "candidate_summary": {
    "focus_topics": ["系统设计", "项目深挖"],
    "reference_summary": ["将重点参考订单系统项目与 JD 中的高并发要求"]
  }
}
```

### 6.4 确定性校验与降级

Planning Agent 输出后，**后端代码**必须校验：

- 边界常量与 §5.1 一致。
- 主题数 4–5（优先生成 5；LLM 输出 6 个时 validator 自动裁至 5），至少 4 个 `required: true`。
- 每个主题字段完整，`id` 唯一，`estimated_minutes` 总和 ≤ 40。
- 校招/社招必须维度（§5.4）至少各命中一次（**维度别名 bucket**，非 regex 硬匹配）。
- `candidate_summary` 不包含完整 `opening_question` 或评分细则。
- Regenerate 时：若存在 `regeneration_feedback`，LLM 输出通过结构校验后执行**策略后验**（见 `regeneration.py` 内 `validate_regeneration_strategy_outcome`）。

**失败处理（借鉴 niumian 重试思路）：**

1. LLM 结构化输出失败或校验/策略后验失败 → 有限重试（最多 3 次，`PlanningAgent`）
2. 仍失败 → **本地岗位模板降级**（按 `interview_type` + `target_role` + `target_level`；`build_template_fallback_plan`）
3. 记录 `trace_id`、重试次数、是否降级、校验失败类别（`agent.py` 内 telemetry 计数 + 日志）
4. 成功落库的 `plan_json.generation_meta` 含 `source` / `generation_attempts` / `degraded` / `degraded_reason`，预览 API 可选返回

### 6.5 代码模块（当前实现）

```text
backend/app/
├── api/routes/interviews.py
├── services/interview_planning_service.py     # 编排：create / generate / regenerate / confirm
├── services/interview_planning/
│   ├── constants.py                           # 边界、策略枚举、LLM 策略说明
│   ├── context.py                             # get_planning_context()（V2 返回空 context）
│   ├── request_validation.py                  # POST 配置与 regenerate 入参校验
│   ├── preview.py                             # 候选人可见预览 + generation_meta
│   └── regeneration.py                        # diff、策略后验、模板降级微调、上一版摘要
├── agent/interview_planning/
│   ├── agent.py                               # LLM 调用、重试、降级、telemetry
│   ├── prompts.py
│   ├── templates.py                           # 模板降级
│   └── validator.py                           # 结构校验 + 维度 bucket
└── schemas/interview_plan.py

frontend/src/
├── pages/InterviewConfigurationPage.tsx       # 02 配置 + 生成（含全屏 Loading 遮罩）
├── pages/InterviewPlanPage.tsx                # 预览、regenerate、confirm
├── components/RegeneratePlanDialog.tsx
├── components/LoadingOverlay.tsx
├── services/interviewPlan.ts
└── types/interviewPlan.ts
```

## 7. 数据、状态与 API

### 7.1 状态与数据职责

```text
planning -> plan_ready -> plan_confirmed
```

- **`interview_sessions`**：一次面试的生命周期容器（谁、配置快照、状态、最终确认的 plan 版本）。
- **`interview_plans`**：计划内容，可有多版本（regenerate 产生 v2、v3…）。

用户点击「生成面试计划」时，后端在一次请求内：**建 session + 写 plan v1**。

### 7.2 状态流转

- 创建会话时进入 `planning`，首次 generate 成功后变为 `plan_ready`。
- 仅 `plan_ready` 可 regenerate / confirm。
- `plan_confirmed` 后由专题 04 激活面试。

### 7.3 独立数据

```text
interview_sessions
interview_plans
```

`interview_sessions` 建议保存：

- 用户 ID、关联 `resume_id`
- 创建时收到的配置快照（JSON）
- 状态、`confirmed_plan_id`

`interview_plans` 建议保存：

- `session_id`、`version`、`status`
- `plan_json`、`candidate_summary_json`
- `regeneration_strategy`、`additional_instruction`（仅 `different_plan` 时有值）
- `created_at`

说明：`focus_topics` 列仍存在于表结构，但 regenerate 路径**不再写入**用户选择的 focus；摘要以创建配置为准。

### 7.4 API

```http
POST /api/interviews
GET  /api/interviews/{session_id}
POST /api/interviews/{session_id}/plan/generate
POST /api/interviews/{session_id}/plan/regenerate
POST /api/interviews/{session_id}/plan/confirm
```

**`POST /api/interviews`**（配置页「生成面试计划」）

- Body：§4.2 配置草稿。
- 行为：校验配置与简历归属 → 创建 `interview_sessions` → **内部调用首次 plan generate** → 写入 `interview_plans` v1 → 更新 session 为 `plan_ready`。
- 响应：一次返回 `session_id`、`candidate_summary`、`topics_preview`、`plan_version`、`regenerations_remaining`、`generation_meta` 等预览字段。

**`POST /api/interviews/{session_id}/plan/regenerate`**

- Body：`{ "regeneration_strategy": "...", "additional_instruction": "" }`
- 仅 `different_plan` 允许非空 `additional_instruction`。
- 达上限返回 429；与当前版本无有效差异返回 409。

**`GET /api/interviews/{session_id}`**

- 返回会话详情与当前计划摘要（不含内部 `opening_question` 等字段）。
- 仍返回 `version_history` 供调试/后续能力；**前端预览页不展示版本历史**（2026-06 产品调整）。

**`POST /api/interviews/{session_id}/plan/generate`**

- 保留，用于首次生成失败后的**重试**，或服务层与 create 共用同一 generate 实现。
- 配置页按钮**不单独调用**此接口；由 `POST /api/interviews` 内部编排。

**不在本专题复用：**

```http
POST /api/interview-configurations/validate
POST /api/interview-configurations
```

## 8. 分步实施

### 小步 1：会话创建与演示计划预览

实现：

- 配置页「生成面试计划」调用 `POST /api/interviews`（含 02 配置草稿；**服务端内含首次 generate**）。
- 服务端校验配置与简历归属。
- 创建新版会话与 `interview_plans` v1；使用最小演示计划数据。
- 前端计划预览页展示候选人计划摘要（路由 `/interviews/:sessionId/plan`）。

不实现：

- 真实 LLM Planning Agent。
- 重新生成和确认。

前端验证：

- 从不合法配置得到明确错误。
- 合法配置进入计划预览，不展示完整问题。

后端验证：

- 会话与计划可持久化恢复。
- 演示计划满足 §5.1 硬边界。

完成条件：

- 02「生成面试计划」按钮接入 03 创建链路。

### 小步 2：真实 Planning Agent 与结构校验

实现：

- 接入 LLM Planning Agent，Prompt 吸收 §5.5 维度与内部分析步骤。
- 结构化输出 + §6.4 代码校验 + 有限重试 + **模板降级**。
- 有 JD / 无 JD、校招 / 社招使用不同 Prompt 分支。
- 基于基础简历解析结果做计划内部分析；不生成用户可见简历分析报告。
- **不接入岗位知识 RAG**；`get_planning_context()` 返回空 context。

不实现：

- 重新生成。
前端验证：

- 校招与社招摘要有可感知差异。
- 有 JD 时 `reference_summary` 体现 JD 重点。

后端验证：

- 非法计划无法持久化。
- LLM 失败可重试或模板降级；降级计划仍须通过 validator。

完成条件：

- 首次计划生成稳定可控。

### 小步 3：重新生成反馈

实现：

- 重新生成弹窗（Portal + 遮罩）、必选策略；**仅 `different_plan` 展示补充说明**。
- 新计划保存为新版本；`regeneration_feedback` 传入 Planning Agent。

完成条件：

- 用户所选策略能定向影响计划（LLM Prompt + 策略后验；模板降级路径下 `apply_regeneration_to_plan` 微调）。

### 小步 4：重新生成上限

实现：

- 最多额外重新生成 **2** 次；按钮与弹窗展示**剩余次数**（`regenerations_remaining`）。
- 后端 `429` 强制上限；409 无有效差异。

说明：版本历史仍由 API 返回，**前端不展示**版本历史列表。

完成条件：

- 次数限制由后端保证；用户可感知剩余次数。

### 小步 5：确认和锁定计划

实现：

- 确认当前版本 → `plan_confirmed` → 保存 `confirmed_plan_id`。
- 锁定后禁止 regenerate（409）。

完成条件：

- 专题 04 可消费不可变已确认计划（`confirmed_plan_id` + `plan_json`）。

### 收尾优化（2026-06，小步 5 之后）

已实现：

- 后端目录拆分（`agent/interview_planning/` + `services/interview_planning/`）。
- 维度校验改为**别名 bucket**；regenerate **加深 diff** + **策略后验**。
- 生成过程 **telemetry**（校验失败类别、降级/outcome 计数）；预览返回 `generation_meta`。
- 重新生成策略收敛为 **6 种**；移除 `adjust_topics`；补充说明仅 `different_plan`。
- 前端：配置页生成 **Loading 遮罩** + 表单禁用；regenerate 弹窗遮罩；侧边栏导航样式修复。

## 9. 测试与验收

已实现测试（CI 通过 `FailingLLMClient` 模拟 LLM 失败，走模板降级路径）：

- `test_interview_planning.py` — API 全流程：create、regenerate 上限、confirm、409/429
- `test_planning_validator.py` — 结构校验、维度、模板降级
- `test_planning_prompts.py` — Prompt/regenerate 块、补充说明仅 different_plan
- `test_regeneration_validator.py` — regenerate 入参校验
- `test_planning_pipeline_optimizations.py` — 维度 bucket、加深 diff、策略后验、generation_meta、telemetry

验收要点：

- 配置草稿校验在 `POST /api/interviews` 完成，非法字段被拒绝。
- 校招、社招、有 JD、无 JD 四类计划均可生成（模板降级路径）。
- 计划满足 §5.1 硬边界与 §5.4 必须维度。
- 计划失败有有限重试、模板降级和明确错误；`generation_meta.degraded` 可观测。
- regenerate 确实改变计划；**最多额外 2 次**；确认后锁定。
- 仅 `different_plan` 可带补充说明；其他策略带说明返回 400。
- 候选人端不泄露完整问题和评分细则。
- LLM + 模板降级仍可生成计划。
- 旧固定四题流程不再作为兼容目标。

## 10. 质量、安全与可观测

- 不记录完整简历、JD 原文、Prompt 和计划内部问题到普通日志。
- 记录 `trace_id`、计划版本、策略、是否降级、校验失败**类别**（`PlanningAgent` telemetry + 结构化日志）。
- 预览 API 返回 `generation_meta`（`source`、`generation_attempts`、`degraded`）；前端类型已同步，**暂未做用户可见降级提示 UI**。
- 简历和 JD 为不可信上下文，不能覆盖系统规则。
- Planning Agent 不能修改会话边界常量（45 分钟、12 轮等）。

## 11. 停止条件

- 计划硬边界只能依赖 Prompt，没有代码校验。
- 重新生成上限只在前端限制。
- 确认后计划仍可修改。
- 校招和社招计划没有可验证差异。
- 对用户展示完整题目清单，偏离计划产品形态。

## 12. 给 AI 的执行指令

```text
阅读 V2/ROADMAP.md、02-interview-configuration-and-jd.md 和本文件。
一次只实现指定小步，不开始动态面试。
Planning Agent 输出必须经过代码校验；V2 不改造 RAG，`get_planning_context()` 恒返回空 context。
不要照搬 niumian 题目清单 Prompt 或 AI 融合简历分析 Prompt。
完成后只更新本文件实施记录。
```

## 13. 实施记录

- 2026-06-08：产品拍板定稿（校验归 03、摘要边界、niumian 选择性借鉴、V2 不改造 RAG、模板降级、POST /api/interviews 内含首次 generate）。
- 2026-06-08：小步 1–2——会话/计划 API、真实 Planning Agent、validator、模板降级、计划预览页。
- 2026-06-08：小步 3–5——regenerate / confirm API、策略反馈、版本递增与 diff 校验、确认锁定、前端弹窗与 react-query。
- 2026-06-08：管道优化——维度 bucket、regenerate 加深 diff 与策略后验、telemetry、`generation_meta`；后端模块拆分与合并。
- 2026-06-08：产品与前端收尾——regenerate 策略改为 6 种（移除 `adjust_topics`）；补充说明仅 `different_plan`；**最多额外 regenerate 2 次**；配置页 Loading 遮罩；regenerate 剩余次数展示；**前端隐藏版本历史**；侧边栏「创建面试」样式修复。
- 2026-06-08：移除 mock 模式；Planning 仅 LLM 主路径 + 失败模板降级；测试改为 `FailingLLMClient`。
- 2026-06-09：Planning 主题数改为 4–5（优先生成 5；6 个自动裁至 5）；`estimated_minutes` 超 40 自动归一化，避免 LLM 重试。

## 14. 收尾状态与未做项

### 14.1 本专题范围内：已完成

| 能力 | 状态 |
|---|---|
| POST /api/interviews 含首次 generate | ✅ |
| plan/generate 重试 | ✅ |
| plan/regenerate + 6 策略 + 上限 2 | ✅ |
| plan/confirm 锁定 | ✅ |
| Planning Agent + validator + 模板降级 | ✅ |
| 候选人计划预览（不含 opening_question） | ✅ |
| regenerate 剩余次数 UI | ✅ |
| 后端测试（降级路径） | ✅ |

### 14.2 本专题明确不做 / 后续专题

| 项 | 说明 |
|---|---|
| 动态面试消费计划 | 专题 04：读 `confirmed_plan_id` + 完整 `plan_json` |
| 用户可见完整题单 | 不符合 V2 产品形态 |
| 内部质量评测面板 | 暂不实现（可选后续工具） |

### 14.3 可选 polish（非阻塞 03 关闭）

- 预览页展示 `generation_meta.degraded` 提示（如「系统降级生成，建议重新生成」）。
- 真实 LLM 路径的集成测试 / 抽样人工评测（CI 默认 `FailingLLMClient` 走模板降级，不测真实模型）。
- `GET /api/interviews` 列表页已由专题 **06** 实现（侧边栏「面试记录」）；03 不再阻塞于列表未开放。
