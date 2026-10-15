# 跨场次学习档案（长期记忆）

## 1. 文档状态

- 状态：**部分已完成**（小步 1–2 + 评估页跨场 UI 已交付；**小步 3 练前右栏暂缓**；不阻塞 01–06 首期）
- 对应路线图：阶段 10
- 核心能力：跨场次学习档案聚合、练前 HITL 推荐（02 右侧栏，**暂缓**）、评估页分区（**本次反馈**：亮点+不足；**与上一场对比** + **练习建议** 两个独立大卡，样式对齐本次反馈）
- 前置专题：[06 评估与练习闭环](./06-evaluation-and-practice.md)（须提供稳定 `evaluation_json` 与 `competencies`）；消费 [05](./05-context-memory-evidence.md) 的 `project_evaluation_memory()` 投影；练前推荐经 [02](./02-interview-configuration-and-jd.md) / [03](./03-planning-and-human-in-the-loop.md) 进入 Planning
- 说明：与 05 本场 `working_memory` 严格分离；**V2 不改造 RAG**
- **首期前端范围（2026-06-11 定稿，2026-06-11 修订）**：**06 评估页**「本次反馈 / 与上一场对比 / 练习建议」已接入；**02 练前推荐（右侧栏）暂缓**；独立趋势页、删会话重算等**本期不做**

## 2. 改造目标

在 V2 首期闭环（**01–06**）稳定后，为**同一用户、同一简历、同一岗位、同一面试类型**的多次模拟面试建立跨场次学习档案，帮助候选人：

- 在评估页看到本场反馈之外的跨场对比与可执行练习建议；
- 在创建面试时（02 配置页）通过右侧练前推荐，**显式采纳**后将历史薄弱方向纳入 `focus_topics`，再进入 03 Planning。

**硬边界：** 长期记忆**不得**进入 04 对话 / Decide / Act / Evidence，**不得**影响 06 本场评分主路径。

## 3. 本专题范围

### 负责（本期）

- 跨场次学习档案的数据模型、SQLite 存储与确定性聚合（`repeat_weak_signals`、`improved_signals`；`topic_trend` 可落库供后续趋势页，**本期前端不展示**）
- 06 评估落库后的 `record_session_outcome()` 写入钩子
- 练前推荐（HITL）：02 配置页**右侧栏**；采纳 / 跳过 / 部分采纳 → `configuration.focus_topics` → 03 Planning
- 06 评估页布局调整：**本次反馈**仅亮点+不足（**移除「改进建议」独立卡片**）；**与上一场对比**（有档案且有效场次 ≥2 时）+ **练习建议**（始终来自 06 单场 `practice_recommendations`，与跨场档案独立展示条件）
- 支撑上述两块所需的 API、后端单测与基础 telemetry

### 延期（本期不做）

- 独立能力趋势页 / 报告内折线图
- 删会话后的 profile 重算与 soft-delete 触发（表结构可预留 `deleted_at`，逻辑后续补）
- 静默注入 Planning Prompt、04 运行时读档案

### 不负责

- 05 本场工作记忆、Evidence Extraction、矛盾检测
- 04 动态追问与 Decide/Act 主逻辑
- 06 单场 Evaluation Agent 与证据驱动评分算法
- V2 岗位知识 RAG / Milvus 公共库改造
- 自动开始新面试
- 输出真实招聘录用结论
- 未经候选人采纳就修改 plan 或 `focus_topics`

## 4. 依赖契约

### 4.1 消费（写入输入）

| 来源 | 字段 | 用途 |
|---|---|---|
| 06 | `evaluation_json.competencies[]` | 各 `topic_id` 的 status / score / confidence |
| 05 | `project_evaluation_memory()` → `evidence_by_topic` | 各主题 `missing_signals`（须为 plan 原文） |
| 03 | `confirmed_plan` / `plan_json` | 主题名、`dimension`、`expected_signals` 词汇对齐 |
| 02 | `configuration` 快照 | `resume_id`、`target_role`、`interview_type`、`focus_topics` |
| Store | `interview_sessions` | `session_id`、`user_id`、`resume_id`、`completed_at`（可用 `updated_at` 推导） |

**聚合维度：** `user_id + resume_id + target_role + interview_type`（换简历视为新档案，不与其他简历场次混算）。

**signal / 主题词汇：** 必须与 plan 的 `expected_signals`、`focus_points` **原文一致**（同 05 §4.6），禁止自造平行 taxonomy。

### 4.2 输出（读取消费）

**向 02 练前推荐（右侧栏，须 HITL 采纳）：**

```json
{
  "session_count": 5,
  "repeat_weak_signals": [
    {
      "signal": "结果指标",
      "topic_dimension": "项目经历",
      "count": 3,
      "last_session_id": "...",
      "suggested_focus_topic": "项目深挖"
    }
  ],
  "improved_signals": [],
  "planning_hints": "多场模拟反复缺少结果指标，可纳入本场重点方向"
}
```

- `suggested_focus_topic`：由后端确定性映射到 02 预定义 `focus_topics` 选项之一，供勾选后写入左侧 focus 选择区。
- 候选人**采纳**后，合并进 `configuration.focus_topics`（仍遵守 02 最多 6 个、不可自由文本规则），再进入 03 生成计划。
- **跳过** = 右侧不勾选任何项直接提交；等价于无历史推荐，Planning 行为与练前右栏未上线时一致。

**向 06 评估页 `GET /api/interviews/{session_id}/learning-context`：**

```json
{
  "has_learning_profile": true,
  "session_count": 5,
  "target_role": "backend",
  "target_role_label": "后端开发",
  "interview_type": "experienced",
  "interview_type_label": "社招",
  "repeat_weak_signals": [],
  "improved_signals": [],
  "cross_session_available": true,
  "session_comparison": {
    "baseline_label": "上一场",
    "baseline_session_id": "...",
    "baseline_completed_at": "...",
    "discussed_coverage": {
      "label": "已考察方向",
      "baseline_count": 3,
      "current_count": 4
    },
    "points": [
      {
        "category": "depth",
        "tone": "better",
        "headline": "回答更全面",
        "detail": "考察点覆盖率 45% → 62%"
      },
      {
        "category": "performance",
        "tone": "same",
        "headline": "已评表现与上场接近",
        "detail": "综合分均为 30"
      },
      {
        "category": "engagement",
        "tone": "worse",
        "headline": "互动偏少",
        "detail": "上场 6 轮 → 本场 4 轮"
      }
    ],
    "summary_line": "相比上场：回答更全面，但互动偏少"
  },
  "practice_cross_session_hints": [
    {
      "topic_id": "topic-1",
      "signal": "结果指标",
      "repeat_count": 3,
      "hint": "结果指标在近 3 场中重复缺失"
    }
  ],
  "repeat_weak_threshold": 2
}
```

- **跨场对比 UI 仅消费 `session_comparison` + `session_count` + 岗位/类型标签**；`cross_session_available === true` 且 `session_comparison.points` 非空时渲染「与上一场对比」大卡。
- **`learning-context` 中 `repeat_weak_signals` / `improved_signals` 固定返回 `[]`**（重复薄弱与改善信号改由练前推荐 API 供给，评估页跨场区块不再展示 signal 列表对比）。
- **`practice_cross_session_hints` 后端已产出，前端尚未并入练习建议卡**（见 §4.7 待办）。
- **练习建议**不依赖本 API 是否有档案；仅读本场 `evaluation_json.practice_recommendations`（及 `question_reviews` 做摘要增强）。
- **本期不展示** `topic_trend` 曲线。

### 4.3 硬禁止（停止条件级）

| 禁止 | 说明 |
|---|---|
| 04 运行时读取学习档案 | Decide / Act / Evidence 只认 `confirmed_plan` + 本场 `working_memory` |
| 06 本场评分读历史 | `competencies` 主路径只用本场 evidence；历史分数不得拉低或抬高本场 |
| 静默改 plan | 未 HITL 采纳不得写入 `focus_topics` 或 Planning Prompt |
| 私有对话入公共库 | 历次 quote 仅用于用户本人报告，不写入岗位知识库 |

### 4.4 与 05 的边界

| | 05 本场工作记忆 | 07 跨场次学习档案 |
|---|---|---|
| 生命周期 | 单会话 `runtime_state.working_memory` | 用户 + 简历 + 岗位 + 校招/社招 |
| 写入时机 | 每轮 reply merge | 06 评估完成后 |
| 读取时机 | 04 Decide / 06 投影 | 02 练前 HITL（暂缓）、06 与上一场对比 / 练习建议 |
| 存储 | `interview_sessions.workflow_state_json` | 独立表 / profile JSON |

### 4.5 与 06 的边界

- **06** 负责评估主路径与 **`practice_recommendations` 单场生成**（`practice_recommendations.py`：从本场 `competencies` / `question_reviews` 推导薄弱主题并映射 `focus_topic`），写入 `evaluation_json`。
- **06 小步 5** 须在 **本专题评估页 UI 未接时即可验收**：后端已产出 `practice_recommendations` 字段。
- **本专题**在 06 评估落库之后挂载 `record_session_outcome()`；负责 `session_comparison`、`practice_cross_session_hints`（hint 前端待接）、练习卡展示与「再练一次」入口，不重复实现单场薄弱项算法。

### 4.6 与 03 的边界

- 03 Planning Agent 主流程不变；07 练前路径只提供**已被候选人采纳**的 configuration 输入（`focus_topics` 快照）。
- 04 激活后只消费 **已确认锁定** 的 `confirmed_plan`，运行时不再查学习档案表。

### 4.7 练习建议（取代独立「改进建议」卡片）

**评估页不再单独展示** `candidate_review.suggestions`（改进建议）。练习建议以**独立大卡**「练习建议」展示（样式对齐「本次反馈」），与「与上一场对比」**并列、互不包裹**。

| 输入（06 `evaluation_json`） | 当前 UI 用法 |
|---|---|
| `practice_recommendations[]` | 主数据：标题（`title`）、`focus_topic`、紧凑长条列表 +「再练一次」 |
| `practice_recommendations[].summary` / `suggested_actions` | 默认摘要；经前端规范化后展示为单行 `summary` |
| `question_reviews[].gaps_and_risks` | **仅当**主建议为「补齐遗漏考察点」类时：解析 `尚未覆盖考察信号：{signal}`，生成 `建议补齐「信号1」「信号2」等遗漏考察点的回答要点`（**最多展示 3 个信号名**，超出加「等」） |
| `candidate_review.suggestions[]` | **本期未并入练习卡**（仍产出，不展示） |
| `question_reviews[].organization_tips` | **本期未并入** |

| 输入（本专题 API，仅有档案时） | 状态 |
|---|---|
| `practice_cross_session_hints[]` | 后端已返回；**前端待接入**（按 `topic_id` 追加跨场小字） |

**首场 / 无学习档案：** 可展示「练习建议」（纯 06）；**不展示**「与上一场对比」。

**有档案且有效场次 ≥2：** 「与上一场对比」与「练习建议」按各自条件**独立渲染**，无「长期行动」总标题。

**摘要文案规则（`buildUnifiedPracticeCards`）：**

- `partially_verified` 且建议含「补齐…遗漏考察点」→ 用 plan 原文信号名展开（见上表）。
- 其他场景（如「重新梳理回答结构」「复盘项目经历准备量化事实」「巩固优势准备反例」）→ **保留** 06 后端 `summary`，不因 `gaps_and_risks` 有遗漏信号而一律改成「补齐要点」。

| 职责 | 归属 |
|---|---|
| 单场薄弱项算法 | **06**（`practice_recommendations.py`） |
| 遗漏信号计数与 `practice_points` 模板 | **06**（`question_reviews.py`） |
| 练习卡 UI + 摘要增强 +「再练一次」 | **本专题前端**（`buildUnifiedPracticeCards.ts`） |
| 跨场场次对比 | **本专题**（`session_comparison.py` + 评估页 UI） |

## 5. 产品规则

### 5.1 用户流程

```text
[同简历 + 同岗位 + 同类型已有 ≥1 场已完成评估 → 存在学习档案]
  ↓
02 配置页：左侧填表 + 右侧「练前推荐」（可跳过）；无档案时保持现网单列
  ↓ 采纳 → focus_topics 合并进 configuration 快照
03 Planning → regenerate / 确认锁定
  ↓
04 面试（不读学习档案）
  ↓
06 评估（本场打分不读历史）
  ↓
评估页：「本次反馈」→「与上一场对比」（可选）→「练习建议」（可选）→ 各维度评价 → JD
  ↓
「再练一次」→ 02 预填 `focus_topic`（练前 HITL 右栏暂缓）
```

### 5.2 练前推荐（HITL）— 02 配置页右侧栏

**页面结构：**

- **无学习档案：** 保持现网**单列**布局，不渲染右栏、不渲染练前推荐相关 DOM（无占位、无空状态文案）。
- **有学习档案且存在可推荐项：** 改为**双栏**（对齐计划页 `v2-plan-layout` 思路）：

```text
┌──────────────────────────── 创建面试 ────────────────────────────┐
│  header（不变）                                                  │
├──────────────────────────────┬──────────────────────────────────┤
│  左栏 · 面试配置（现有表单）    │  右栏 · 练前推荐                   │
│  简历 / 类型 / 岗位 / 难度      │  checkbox 列表 + 说明文案          │
│  JD 文本                       │  勾选 → 同步高亮左侧 focus 按钮    │
│  系统推荐重点方向（focus）      │  「纳入重点只影响考什么，不影响评分」 │
│  [生成面试计划]                 │                                   │
└──────────────────────────────┴──────────────────────────────────┘
```

**规则：**

- 右栏**仅当** `has_learning_profile === true` **且** `repeat_weak_signals` 非空（或 API 等价 `recommendations_available === true`）时渲染；否则整页与练前右栏未上线时像素级一致（单列）。
- 展示重复 weak signal（plan 原文）+ `topic_dimension` + 出现次数；勾选后映射并合并进左侧 `focus_topics`（用户仍可手动取消）。
- 文案须说明：**纳入重点只影响考什么，不影响本次评分标准。**
- 不勾选任何推荐项即视为跳过；不得残留未采纳的 `focus_topics` 注入。
- `resume_id` / `target_role` / `interview_type` 变化时重新请求推荐 API（档案键变化可能导致 `has_learning_profile` 变为 false）。

**响应式：** 仅有档案且展示右栏时，窄屏（≤760px）折叠到左栏 `focus_topics` **上方**；无档案时不插入任何折叠块。

### 5.3 评估页布局 —「本次反馈」「与上一场对比」「练习建议」

总览卡之后为三个**同级独立白底大卡**（标题 + 一行说明 + 内容区，样式对齐「本次反馈」）。**已移除「长期行动」总标题**与「改进建议」独立双栏卡片。

```text
总览卡（综合分 + 覆盖）
│
├─ 【本次反馈】大卡
│    └─ 亮点 | 主要不足
│
├─ 【与上一场对比】大卡（可选）
│    ├─ 标题行：与上一场对比 | 右侧摘要标签（去掉「相比上场：」前缀）
│    ├─ 左栏：已考察方向 — 上一场 X 个 / 本场 Y 个
│    └─ 右栏：固定 3 条变化（图标 + 一行：headline，detail）
│
├─ 【练习建议】大卡（可选）
│    └─ 紧凑长条列表：标题 + summary + [再练一次]
│
├─ 【各维度评价】大卡（Tab 与详情同一 workspace，选中 Tab 与下方内容视觉一体）
├─ JD 匹配
└─ footnote
```

**「本次反馈」**

- 只展示 `highlights` 与 `weaknesses`。
- **不渲染** `candidate_review.suggestions`。

**「与上一场对比」**

| 项 | 规则 |
|---|---|
| 展示条件 | `learningContext.cross_session_available === true` 且 `session_comparison.points.length > 0` |
| 有效场次 | 仅统计**真正进行过面试**的 completed 场次（`discussed_topics > 0` 或 `scored_topics > 0` 或 `user_answer_rounds > 0`）；对比基准为**上一场有效场次** |
| 左栏 | `discussed_coverage`：上一场 / 本场 **已考察方向数**（`discussed_topics`） |
| 右栏 3 维 | `depth` 回答全面性（覆盖率差 ≥12%）、`performance` 已评表现（两场均有分且分差 ≥8）、`engagement` 互动投入（轮次差 ≥3）；不足阈值则为 `same`；无法对比为 `unavailable` |
| 摘要标签 | `summary_line` 去掉「相比上场：」后置于标题右侧；`tone` 映射：提升 / 待提升 / 持平 |
| 变化行文案 | `headline` 与 `detail` 合并为一行（如「回答更全面，考察点覆盖率 45% → 62%」），保留状态图标 |

**「练习建议」**

| 项 | 规则 |
|---|---|
| 展示条件 | `practice_recommendations` 非空（经 `buildUnifiedPracticeCards`） |
| 数据来源 | **仅本场** 06 数据；**不读** `learning-context`（跨场 hint 待接） |
| 单条结构 | `title` + 单行 `summary` +「再练一次」（跳转 02 预填 `focus_topic`） |
| 摘要增强 | 见 §4.7；非「补齐遗漏考察点」类保留 06 原话术（如准备项目、重新梳理结构等） |

**练习建议单条示意：**

```text
加强「项目深挖」
「结果指标」仍薄弱，建议补齐「结果指标」「个人贡献」等遗漏考察点的回答要点     [ 再练一次 ]
```

### 5.4 无档案 / 首场时的展示规则（硬性）

**02 配置页（不变）：** 无学习档案 → 单列，零练前推荐 DOM。

**06 评估页（区分跨场 vs 练习）：**

| 场景 | 与上一场对比 | 练习建议 | 改进建议独立卡 |
|---|---|---|---|
| 首场 / 无有效上一场 | 不展示 | 展示（仅 06） | 不展示 |
| 有效场次 < 2 | 不展示 | 展示（06） | 不展示 |
| `cross_session_available === false` | 不展示 | 展示（06） | 不展示 |
| 有效场次 ≥2 且对比可算 | 展示 | 展示（06） | 不展示 |
| 本场无 `practice_recommendations` | 按左列 | 不展示 | 不展示 |
| `learning-context` 加载中/失败 | 不展示 | 仍可用 06 展示 | 不展示 |

**禁止：**

- 无跨场条件时展示「与上一场对比」或空状态占位（「暂无历史」等）。
- 02 无档案时右栏占位或假双栏。
- 保留「改进建议」独立双栏卡。
- 用跨场档案改写练习建议主文案（练习建议始终本场生成）。

**允许：** 首场仅展示「练习建议」；跨场与练习**独立出现**，互不依赖。

### 5.5 数据隔离

- 档案按 `user_id + resume_id + target_role + interview_type` 隔离；学习档案 API 须校验 `user_id` 与 `resume_id` 归属，仅本人可读。

### 5.6 延期规则（本期不验收）

- 删会话后的 outcome 软删与 profile 重算（见 §3 延期）。
- 独立趋势页与 `topic_trend` 图表展示。

## 6. 技术设计

### 6.1 存储（建议）

```sql
CREATE TABLE user_learning_profiles (
  user_id INTEGER NOT NULL,
  resume_id TEXT NOT NULL,
  target_role TEXT NOT NULL,
  interview_type TEXT NOT NULL,
  profile_json TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (user_id, resume_id, target_role, interview_type)
);

CREATE TABLE learning_session_outcomes (
  id TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL,
  resume_id TEXT NOT NULL,
  session_id TEXT NOT NULL UNIQUE,
  target_role TEXT NOT NULL,
  interview_type TEXT NOT NULL,
  completed_at TEXT NOT NULL,
  outcome_json TEXT NOT NULL,
  deleted_at TEXT
);
```

`profile_json` 含 `repeat_weak_signals`、`improved_signals`、`topic_trend`（趋势页后续用）；`outcome_json` 保存单场快照（competencies 摘要 + missing_signals）。

### 6.2 模块（建议）

```text
backend/app/services/learning/
  schema.py              # 阈值：REPEAT_WEAK_THRESHOLD、跨场对比差分阈值
  aggregate.py           # repeat_weak_signals、improved_signals、topic_trend
  session_summary.py     # 单场 session_summary、有效场次判定
  session_comparison.py  # build_session_comparison() → discussed_coverage + 固定 3 points
  eligibility.py         # filter_eligible_outcome_rows
  record.py              # record_session_outcome()
  query.py               # get_learning_recommendations / get_learning_context_for_session
  planning_hints.py      # 练前推荐文案 + signal→focus_topic

backend/app/db/store.py
  # user_learning_profiles、learning_session_outcomes

frontend/src/pages/InterviewEvaluationPage.tsx
  # SessionFeedbackSection / CrossSessionComparisonSection / PracticeRecommendationsSection / DimensionEvaluationSection
frontend/src/utils/buildUnifiedPracticeCards.ts
frontend/src/hooks/useInterviewLearning.ts
frontend/src/App.css
  # v2-eval-cross-session-*、v2-eval-practice-*、v2-eval-dimension-workspace

frontend/src/pages/InterviewConfigurationPage.tsx   # 练前右栏 — 暂缓

backend/tests/test_learning_step1.py
backend/tests/test_learning_session_comparison.py
backend/tests/test_learning_eligibility.py
```

### 6.3 API（本期）

```http
GET  /api/users/me/learning-recommendations?resume_id=...&target_role=...&interview_type=...
GET  /api/interviews/{session_id}/learning-context   # 评估页跨场对比；按会话 resume_id 查档案；返回 session_comparison
```

说明：

- 练前推荐用 `learning-recommendations`，**必填** `resume_id`（02 当前选中简历）；无档案时返回 `{ "has_learning_profile": false }`（**不要**返回空列表冒充有数据）。
- 评估页 `learning-context` 无档案或有效场次不足时 `cross_session_available: false`；前端**仅跳过「与上一场对比」**；练习卡仍从 `evaluation.practice_recommendations`（+ `question_reviews` 摘要增强）。
- 响应须含 `has_learning_profile`（或 HTTP 204 / 省略字段并由前端视为 false），实施时二选一并写死。
- 写入由 06 evaluate 成功路径内部调用 `record_session_outcome()`，不暴露候选人 write API。

### 6.4 聚合规则（确定性，须单测）

- **repeat_weak_signal**：同一 signal 原文在 N 场 outcome 的 `missing_signals` 中出现 ≥2 次（阈值可配置，默认 2）。
- **improved_signal**：仅统计**实际讨论过**的主题（`discussed` / 有 evidence）；按 **dimension 桶 + signal** 对齐；先前在讨论主题中 missing、且最新一场**同维度再次被考察**且该 signal 已不在 missing、且仍在本场 plan 预期信号内 → 归入改善；按 dimension **合并展示**，最多 5 组；文案「本轮已覆盖」。
- **topic_trend**：按 `completed_at` 追加每场各 `topic_id` 的 status / score（**本期仅落库，前端不展示**）。
- **signal → focus_topic**：确定性映射到 02 预定义选项；禁止 LLM 临场编造历史统计。
- **session_comparison（评估页跨场 UI）**：
  - 对比对象：当前场次 outcome vs **上一场有效场次** outcome（非简单「上一条 DB 记录」）。
  - `discussed_coverage`：`discussed_topics` 上一场 vs 本场。
  - 固定 **3** 条 `points`：`depth` / `performance` / `engagement`；`tone` 为 `better` | `worse` | `same` | `unavailable`。
  - 阈值见 `schema.py`：`SIGNAL_COVERAGE_RATE_DELTA_THRESHOLD=0.12`、`PERFORMANCE_SCORE_DELTA_THRESHOLD=8`、`ROUNDS_DELTA_THRESHOLD=3`。
  - `summary_line` 供前端摘要标签；列表行展示 `headline` + `detail` 合并文案。

## 7. 分步实施

### 小步 1：Schema + Store + 评估后写入

实现：

- 表结构与 `learning/` 模块骨架。
- 06 评估落库成功后调用 `record_session_outcome()`。
- 从 `evaluation_json` + `project_evaluation_memory()` 生成 outcome 快照并 upsert profile。
- `GET learning-recommendations` 与 `GET learning-context`（或扩展 evaluation 响应）骨架。

不实现：

- 前端、练前 HITL、评估页跨场/练习 UI。

后端验证：

- 连续 2 场模拟后 `repeat_weak_signals` 计数正确。
- signal 与 plan 原文一致；`suggested_focus_topic` 落在 02 合法选项内。

完成条件：

- 跨场数据可写入、可查询；06 无 07 档案时评估页跨场模块不展示。

### 小步 2：评估页「本次反馈 / 与上一场对比 / 练习建议」

实现：

- `InterviewEvaluationPage`：本次反馈大卡（亮点|不足）；**移除改进建议独立卡**。
- **与上一场对比**独立大卡：`session_comparison` 双栏（已考察方向数 + 3 条变化）；标题右侧摘要标签。
- **练习建议**独立大卡：紧凑长条 + `buildUnifiedPracticeCards`（06 `practice_recommendations` + `question_reviews` 信号名摘要增强）。
- `useInterviewLearningContext`；跨场展示门控 `cross_session_available`。
- **各维度评价**：Tab 与详情 `v2-eval-dimension-workspace` 一体布局。

不实现：

- `practice_cross_session_hints` 并入练习卡；`suggestions` / `organization_tips` 融合。
- 02 练前右栏。
- 趋势图、删会话重算。

前端验证：

- 首场可见练习建议（06），不可见与上一场对比。
- 第二场有效场次且对比可算后可见与上一场对比。
- 练习摘要：「补齐遗漏考察点」类展示信号名（≤3 +「等」）；其他类保留 06 原话术。
- 「再练一次」跳转 02 预填 `focus_topic`。

完成条件：

- 评估页三块可独立验收；06 单场闭环仍独立可跑。

### 小步 3：02 配置页练前推荐（右侧栏）→ Planning — **暂缓**

后端 `GET learning-recommendations` 与 `useLearningRecommendations` hook 已就绪；**配置页尚未接入**。

计划实现：

- `InterviewConfigurationPage` 在有档案且可推荐时启用双栏；无档案时保持单列。
- 勾选推荐 → 同步左侧 `focus_topics`。
- 窄屏右栏折叠至 focus 上方。

完成条件（待做）：

- 练前推荐 HITL 闭环可用。

### 延期小步（后续专题迭代，本期不实施）

| 原小步 | 内容 |
|---|---|
| 小步 4 | 独立能力趋势页 / `topic_trend` 图表 |
| 小步 5 | 删会话 soft-delete outcome + profile 重算 |

## 8. 测试与验收

- 07 未上线或仅有单场时，01–06 全链路验收标准不变。
- 写入与聚合为确定性逻辑，有单测；不依赖 LLM。
- 04 Decide 代码路径无 `learning_profile` / `get_learning_profile` 引用（可通过 grep 验收）。
- 06 评分主路径无历史分数输入（可通过 evaluate 输入契约验收）。
- 练前推荐须 HITL；跳过时不改 configuration。
- signal / topic 词汇与 plan 对齐，无自造维度。
- 按 user + resume_id + role + interview_type 隔离；换简历不串档案。
- **本期前端**：02 右栏 + 评估页两分区验收通过即可；不验收趋势页与删会话重算。
- **02 无档案：** 与练前右栏未上线时一致，无右栏。
- **06 首场：** 可有练习建议（06），无与上一场对比；无改进建议独立卡。
- **跨场对比：** 使用 `session_comparison`，非 `repeat_weak_signals` 列表 UI。

## 9. 质量、安全与可观测

- 普通日志不记录完整 outcome_json 或跨场 quote 原文。
- 记录：`record_session_outcome` 耗时、profile 版本。
- 学习档案仅本人可读；API 须校验 `user_id`。
- 学习档案开关与 V2 RAG 改造无关；07 关闭或仅有单场时不影响 03/04/06 主路径。

## 10. 停止条件

- 长期记忆在 04 对话或 06 本场评分中被读取。
- 未经采纳就修改 plan 或 `focus_topics`。
- 历史低分导致本场 competency 降分。
- repeat_weak_signal 使用 plan 外自造标签。
- 将候选人历次回答写入 Milvus 或公共岗位知识库。
- 无跨场条件时渲染「与上一场对比」、跨场 hint 或空状态占位；或同时保留改进建议独立卡。
- 02 无档案时仍渲染练前推荐右栏或占位双栏。

（删会话 profile 串库等规则在延期小步启用后再纳入停止条件。）

## 11. 给 AI 的执行指令

```text
阅读 V2/ROADMAP.md、05-context-memory-evidence.md、06-evaluation-and-practice.md 和本文件。
确认 01–06 首期闭环已稳定；07 剩余项（练前右栏、趋势页等）可迭代交付。
一次只实现一个小步（本期仅小步 1–3）。
写入钩子在 06 评估落库之后；读取仅在 02 练前右栏（暂缓）、06 评估页 `learning-context`（跨场）与 06 报告（练习建议）。
评估页布局：总览 → 本次反馈 → 与上一场对比（可选）→ 练习建议（可选）→ 各维度评价 → JD。无「长期行动」总标题。
跨场对比读 session_comparison；练习建议读 06 practice_recommendations，见 §4.7。
02 练前右栏暂缓；有 API 无配置页 UI。
06 无跨场条件时禁止「与上一场对比」；允许独立「练习建议」（纯 06）。
禁止在 decide.py、act.py、extract_evidence、06 评分主路径中读取 learning_profile。
不要修改 05 working_memory Schema。
不要实现趋势页、删会话重算（已延期）。
```

## 12. 实施记录

- 2026-06-11：**小步 1 完成** — `backend/app/services/learning/`（schema / aggregate / record / query / planning_hints）；Store 表 `user_learning_profiles`、`learning_session_outcomes`；06 评估 `completed` 后 `record_session_outcome()`；`GET /api/users/me/learning-recommendations`、`GET /api/interviews/{session_id}/learning-context`；`tests/test_learning_step1.py`。
- 2026-06-11：**小步 2 首版** — 评估页「本次反馈」「长期行动」；`buildUnifiedPracticeCards`；`useInterviewLearning` + 跨场对比。
- 2026-06-11：**小步 3 暂缓** — 练前推荐 API/hook 就绪，配置页右栏未接。
- 2026-06-11：**范围收窄** — 前端首期以 06 评估页为主；02 练前右栏暂缓；独立趋势页与删会话重算延期。
- 2026-06-11：**无档案不展示（02）** — 配置页无档案时不渲染练前右栏。
- 2026-06-11：**聚合维度** — `user_id + resume_id + target_role + interview_type`。
- 2026-06-11：**评估页布局定稿（首版）** — 本次反馈仅亮点+不足；长期行动=跨场对比+练习建议。
- 2026-06-11：**跨场对比模型改版** — 由 signal/主题对齐改为 **场次摘要对比**（`session_comparison.py` + `session_summary.py` + `eligibility.py`）；`discussed_coverage` + 固定 3 维变化点；`learning-context` 评估页不再返回 `repeat_weak_signals` / `improved_signals`。
- 2026-06-11：**评估页 UI 改版** — 移除「长期行动」总标题；**与上一场对比** / **练习建议** 各为独立大卡（对齐本次反馈白底样式）；跨场摘要标签在标题右侧；变化行图标+单行文案；各维度 Tab/详情 `dimension-workspace` 一体。
- 2026-06-11：**练习建议摘要** — `buildUnifiedPracticeCards` 在「补齐遗漏考察点」类建议下，从 `question_reviews.gaps_and_risks` 解析 plan 原文信号（最多 3 个 +「等」）；其他场景保留 06 `summary`（准备项目、重新梳理等）。`practice_cross_session_hints` / `suggestions` 融合仍待做。
- 2026-06-11：**07 部分交付对齐** — 状态改为「部分已完成」；移除 RAG 专题引用；统一 07=跨场次编号；评估页跨场（小步 1–2）与 06 文档对齐。
