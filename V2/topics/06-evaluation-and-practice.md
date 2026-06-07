# 评估与练习闭环

## 1. 文档状态

- 状态：**首期已完成**（小步 1–5 + 小步 1 补全 + 2026-06-11 体验/校准迭代）
- 对应路线图：阶段 9
- 核心 Agent：Evaluation Agent
- 前置专题：04 动态面试 Agent、05 上下文/记忆/证据；跨场次展示消费 [07 跨场次学习档案](./07-cross-session-learning.md)（**07 小步 1–2 已交付**评估页对比；练前 HITL 仍属 07 暂缓项）

## 2. 改造目标

根据本场面试积累的证据生成可解释评估，让候选人知道表现如何、结论依据是什么、哪些能力未验证，以及下一次应该如何练习。

## 3. 本专题范围

### 负责

- Evaluation Agent
- 总体表现、能力维度评分和置信度
- 证据引用
- 风险和未验证项
- 有 JD 时的匹配分析
- 逐题复盘
- 改进建议和专项练习入口（**本场**；评估页跨场对比 UI 消费 07 API，见 §3 不负责）
- **面试记录列表**（`/interviews`）：V2 会话摘要、状态与进入计划/对话/评估的入口
- 评估页渲染 07 提供的「与上一场对比」（有档案且满足条件时）
- 评估页面、数据、API、测试和日志

### 不负责

- 面试过程证据提取
- 跨场次档案写入/聚合、能力趋势页、练前 HITL 推荐（专题 **07**；06 仅**展示** 07 的 `learning-context`）
- 动态追问
- 输出真实招聘录用结论
- 跨场次 repeat/improved 信号汇总与 profile 维护（07）；06 不实现趋势图

## 4. 依赖契约

### 4.1 消费

- 专题 03：不可变 `confirmed_plan` / `plan_json`（主题 `id`、`dimension`、`name`、`evaluation_criteria` 等）。
- 专题 04：完整问答（按 `messages.meta.topic_id`）、主题覆盖、`runtime_state`、面试完成状态。
- 专题 05：`evidence_by_topic`、`risks`、`unverified_items`（**评分主路径**）。
- 专题 02：`configuration.jd_text` 原文（**非**结构化 JD；有 JD 时展示匹配分析）。
- 专题 03：已锁定计划中 `source_refs` 含 `jd:` / `jd：` 的主题，作为 06 JD 匹配的**要点范围**（见 §4.3）。
- 专题 **07**（可选）：`GET .../learning-context` 供评估页「与上一场对比」；无档案时不展示该模块。
- 向专题 02 提供可选的下次练习预填方向（**本场薄弱项**）；跨场练前预填见 **07**（暂缓）。
- `evaluation_anchors`：V2 由 05 投影为空，06 使用**本地评分锚点**降级。

### 4.2 与 plan_json / 05 对齐（硬要求）

**评估维度 = plan 主题，不是第二套 taxonomy。**

| 报告展示 | 数据来源 | 禁止 |
|---|---|---|
| 能力/主题项 `topic_id`、`name` | plan 主题 | 自造与 plan 无关的能力名列表 |
| `dimension` | plan 主题 `dimension` | 另建 niumian 式六大维度主表 |
| 评分依据 | 05 `evidence_by_topic[topic_id]` + plan `evaluation_criteria` | 评估时全文重读聊天「现编证据」 |
| 未验证 | 05 `unverified_items` 或 signal 无足够 evidence | 把未覆盖写成低分或「不符合」 |
| 逐题复盘 | 按 plan 主题顺序；引用 05 quotes | 按 V1 题号线性复盘 |

**输入优先级：**

1. **主路径**：`confirmed_plan` + `evidence_by_topic` + `risks` + `unverified_items`。
2. **兜底**：04 `messages`（按 `topic_id` 分组）仅在 05 证据缺失或 quote 校验失败时用于补原文，**不得**替代 05 结构化证据做主要打分依据。
3. **禁止**：以旧 V1 `question_threads` 或 niumian `question_history_list` 形态作为主输入契约。

**输出 `competencies[]` 与 plan 一一对应：**

- 每个 plan 主题至少一条 competency；`topic_id`、`name`、`dimension` 与 plan 一致。
- `status`（verified / partially_verified / unverified）由该主题 `expected_signals` 在 05 中的覆盖度 + evidence `strength` 确定性推导；模型只可建议，后端须校验。
- `score` 仅当 `status` 为 verified 或 partially_verified 时允许；`unverified` 不得有确定分数。
- `evidence_references` 必须来自 05 已存 quote；引用须能在 `evidence_by_topic` 或 messages 中回溯。

**`question_reviews[]`：** 与 plan 主题同序同 id；`考察目的` 来自 plan `objective` / `dimension`，不得写入 plan 未覆盖的新考察方向。

**一致性验收：**

1. 报告中主题数量、顺序、`topic_id` 与 `confirmed_plan.topics` 一致。
2. 每项 competency 的 `dimension` 等于 plan 对应主题 `dimension`。
3. 无 evidence 的主题不会被赋予确定低分或高分。
4. 逐题复盘中的 quote 可在 05 evidence 或 messages 中找到。

### 4.3 借鉴 niumian 评估的边界

niumian 评估 Prompt 成熟之处：**必须引用原话**、**简历一致性/前后矛盾**检查、**未验证 vs 低分**区分。可借鉴这些**产品规则**写入 06 Prompt 与校验。

| 可借鉴 | 本专题映射 |
|---|---|
| 每项评价引用候选人原话 | `evidence_references` 必须链到 05 quote |
| 简历描述 vs 回答一致性 | JD/简历匹配段 + 05 `risks` |
| 前后回答一致性 | 消费 05 `contradictions` / risks，不重新发明矛盾引擎 |
| 校招/社招不同评价重点 | 读 `configuration.interview_type` + plan `dimension` |
| 量化扣分规则表述 | 可选写入本地 `evaluation_anchors` 降级模板 |

| 不应借鉴 | 原因 |
|---|---|
| niumian 独立六大维度作为主评分维度表 | 与 03 plan 主题重复，易割裂 |
| 评估时再全文解析 `interview_record` 作主路径 | 05 已负责过程证据；06 消费结构化结果 |
| niumian 0–100 分制与冗长扣分表原样照搬 | V2 使用 1–5 分 + 置信度 + 确定性聚合 |
| 输出标准答案/参考回答全文 | 与 §5.4 逐题复盘边界冲突 |

### 4.4 旧能力处理边界

- 直接保留：LLM Factory、模型配置、通用结构化输出、日志和基础 RAG 设施。
- 允许抽取：不包含旧教学版评分规则的通用报告生成、结构化校验或展示组件。
- 替换重构：Evaluation Agent、证据驱动评分、JD 匹配、未验证项、逐题复盘、练习建议、新版评估数据和页面。
- 允许破坏：旧按回答数量和长度计算的评估逻辑、旧评估 Schema 和旧面试会话表可以被替换。
- 验证要求：新版面试完成、证据驱动评估和评估页展示稳定。

## 5. 产品规则

### 4.1 报告结构

报告至少包含：

- 总体表现摘要
- 本次覆盖情况
- 评估置信度
- 各能力维度表现（**与 plan 主题一一对应**，见 §4.2）
- 每项能力的证据引用
- 风险和未验证项
- 有 JD 时的「本场 JD 要点验证」（见 §4.3）
- 逐题复盘
- 下一步练习建议

### 4.2 评分规则

- 能力评分使用 1 至 5 分；前端展示为 `score × 20`（满分 100）。
- 每项评分必须包含置信度。
- 高分或低分必须引用证据。
- 没有足够证据时标记为未验证，不直接给低分。
- **`partially_verified` 只表示「本场有讨论/有部分证据」，不等于「表现尚可」**：分数绑定正向证据与信号覆盖率，**无 2 分（40 分）地板**。
- **负面证据加重惩罚**（如明确未掌握核心技能）；以负面为主、无正向证据时，允许落到 **1 分（20 分）**。
- **展示标签按分数分档**（与 `status` 解耦）：≤2「明显不足」、3「仍有明显缺口」、≥4「有亮点待加强」；低分维度 UI 使用红色 `low` tone，覆盖侧栏标「未达标」。
- 总体结果根据已验证能力计算，同时展示覆盖率（含 `discussed_topic_count` / `scored_topic_count`）。
- 校招和社招使用不同评价重点。
- 不按回答长度直接评分。
- 不输出“录用、拒绝”等真实招聘结论。

### 4.3 JD 匹配（本场要点验证）

**展示前提：** 仅当 `configuration.jd_text` 非空时生成并展示 `jd_match`；无 JD 时 `jd_match: null`，前端不渲染空模块。

**要点范围（硬约定）：** 评估侧**不对 JD 原文逐条解析**。JD 要点来自 **03 已锁定计划** 中 `source_refs` 以 `jd:` / `jd：` 开头的主题（每个 topic 至多一条 `display_requirement`）。Planning Agent 在有 JD 时应把对齐要求写入对应主题的 `source_refs`；若提供了 JD 但计划未标注任何 `jd:` 主题，仍返回 `jd_match` 对象，但 `requirement_count = 0`，摘要提示「本场计划未标注与 JD 对应的考察方向」。

**三档分类（与 plan 主题 + 05 证据联动）：**

| 桶 | 含义 | 判定依据（概要） |
|---|---|---|
| `verified_aligned` | 已验证且符合 | 对应 competency 为 `verified`，无 risks/负面证据 |
| `verified_with_risk` | 已验证但存在风险 | `partially_verified`，或存在 risks/负面证据 |
| `unverified` | 尚未验证 | competency 为 `unverified`，或证据不足以形成结论 |

不能把「尚未验证」表达为「不符合」。前端模块标题为「本场 JD 要点验证」，以 checklist + 统计（已验证 / 有风险 / 尚未验证）展示，并附免责声明。

### 4.4 逐题复盘

每个 **plan 主题**至少展示（`topic_id` 与 plan 一致）：

- 考察目的
- 回答中的有效信息
- 遗漏或风险
- 更好的回答组织方式
- 推荐练习点

首期不生成长篇标准答案，避免候选人机械背诵。

## 6. Evaluation Agent 设计

### 5.1 输入

```json
{
  "configuration": {},
  "confirmed_plan": {},
  "messages_by_topic": {},
  "evidence_by_topic": {},
  "risks": [],
  "unverified_items": [],
  "jd_text": "",
  "structured_jd": null,
  "evaluation_anchors": []
}
```

- `confirmed_plan`：专题 03 锁定计划全文；competency 与 question_reviews 的**维度与主题名唯一来源**；JD 要点范围来自其中 `source_refs` 的 `jd:` 项。
- `jd_text`：来自 `configuration.jd_text`；**仅作是否有 JD 的门控**（非空才生成 `jd_match`），不参与逐条要求抽取。
- `structured_jd`：V2 首期恒为 `null`（无独立 JD 结构化解析）。
- `evidence_by_topic`：专题 05 输出；**评分与证据引用主路径**。
- `messages_by_topic`：由 04 `messages` 按 `meta.topic_id` 分组；仅 quote 兜底与复盘展示，非主评分输入。
- ~~`question_threads`~~：旧 V1 形态，**不得**作为 V2 评估主契约。

### 5.2 输出

```json
{
  "overall_score": 78,
  "coverage_rate": 0.8,
  "overall_confidence": 0.76,
  "summary": "...",
  "competencies": [
    {
      "topic_id": "topic-1",
      "name": "系统设计",
      "dimension": "方案取舍或系统设计",
      "status": "verified",
      "score": 4,
      "confidence": 0.8,
      "strengths": [],
      "risks": [],
      "evidence_references": []
    }
  ],
  "jd_match": null,
  "unverified_items": [],
  "question_reviews": [],
  "practice_recommendations": []
}
```

有 JD 时 `jd_match` 示例：

```json
{
  "has_jd": true,
  "requirement_count": 2,
  "verified_aligned": [
    {
      "requirement": "熟悉 Java 微服务开发",
      "topic_id": "topic-1",
      "topic_name": "Java 微服务",
      "evidence_quotes": ["我负责 Java 微服务核心模块开发"],
      "note": null
    }
  ],
  "verified_with_risk": [],
  "unverified": [
    {
      "requirement": "Agent 核心能力",
      "topic_id": "topic-3",
      "topic_name": "Agent 核心能力",
      "evidence_quotes": [],
      "note": "本场未充分讨论该主题。"
    }
  ],
  "summary": "本场对齐 2 条 JD 要点：1 条已验证，1 条尚未验证。"
}
```

`competencies` 条数应与 `confirmed_plan.topics` 一致（或明确标注跳过原因）；`dimension` 必须来自 plan，不可由模型自由命名。

能力 `status`：

```text
verified
partially_verified
unverified
```

### 5.3 代码校验

- 分数范围 1 至 5。
- 置信度范围 0 至 1。
- `unverified` 能力不能拥有确定分数。
- 所有证据引用必须能在 05 `evidence_by_topic` 中找到；messages 仅作二次兜底。
- 每个 competency 的 `topic_id`、`name`、`dimension` 与 `confirmed_plan.topics` 中对应项一致。
- `jd_match` 仅当 `configuration.jd_text` 非空时生成；要点来自 plan `source_refs` 的 `jd:` 项，**不**从 JD 原文逐条抽取。
- 总体分数计算不能完全由模型自由给出；应由能力评分、计划权重或确定性聚合规则生成。

### 5.4 评估页加载与展示契约

**数据拉取（`useInterviewEvaluationReport`）：**

1. **优先** `GET /api/interviews/{session_id}/evaluation`；已有 `evaluation_json` 则直接展示，**不**因 session 仍为 `evaluating` 而重复 `POST /evaluate`。
2. 仅当 GET 无报告且 session 为 `evaluating` 时，才 `POST /evaluate` 触发生成。
3. Query `staleTime` 建议 ≥ 30s，避免无意义 refetch。

**Loading 态（定稿）：**

- 全页「正在生成面试反馈」**仅**在 `isPending && !report`（或等价：首屏尚无报告）时展示。
- **禁止**用 `isFetching` 遮挡已展示报告；后台 refetch 时报告应持续可见。
- 记录列表已「已结束 / 评估中」且 GET 能拉到完整数据时，进入评估页不得长期卡在 loading。

**覆盖提示：**

- 「你聊到 X 个」使用 `discussed_topic_count`（≥ 已评 / 有证据 / 已完成主题的最大值）；手动结束须将 `current_topic_id` 写入 `completed_topic_ids`。
- 前端优先用实时计算的 `coverage_note`，避免缓存旧文案。

## 7. 数据、状态与 API

### 6.1 状态

```text
active -> evaluating -> completed
```

评估失败时保持可重试状态，不应丢失面试记录。

### 6.2 数据

建议保存 `evaluations`：

- `session_id`
- `version`
- `status`
- `evaluation_json`
- `model_info`
- `created_at`

支持重新评估时保留版本，但首期不向候选人提供无限重新评估按钮。

### 6.3 API

```http
GET  /api/interviews                              # V2 会话列表（面试记录）
POST /api/interviews/{session_id}/evaluate
GET  /api/interviews/{session_id}/evaluation
GET  /api/interviews/{session_id}/evaluation/history
POST /api/practice/from-evaluation
```

`GET /api/interviews` 返回当前用户 V2 会话摘要（含 `status`、更新时间、是否已有 `evaluation`），供侧边栏「面试记录」与评估入口使用；**不**返回跨场趋势或完整学习档案（聚合见 **07**）。

按实施小步逐步增加，不提前创建全部空接口。

## 8. 分步实施

### 小步 1：最小评估页面与演示数据

实现：

- 面试结束后生成结构化报告。
- 展示总体摘要、覆盖情况、优势、风险和未验证项。
- 使用最小演示数据验证页面结构和状态闭环。

不实现：

- 正式能力评分。
- JD 匹配和逐题复盘。

前端验证：

- 完成面试后进入新版评估页。
- 未验证项与风险分开展示。

完成条件：

- 评估页面和状态闭环可用（结束面试后遮罩提示 → 3 秒后进面试记录页）。
- **完整用户闭环**还需 **小步 1 补全**（面试记录列表 + 轮询 + 从记录进入评估/继续面试）。

### 小步 1 补全：面试记录与评估入口

**动机：** 评估（尤其小步 2 起 LLM 路径）通常**不是瞬时完成**；用户会离开再回来，主路径应是 **侧边栏「面试记录」→ 点会话 → 看状态/进评估**，而不是仅依赖结束面试时的自动跳转。

#### 持久化说明（回答「计划有没有存」）

- **02 配置页草稿**：未点「生成面试计划」前**不持久化**（关页即丢）。
- **03 起会话 + 计划**：用户提交 `POST /api/interviews` 后，**会话**（`interview_sessions` + `configuration_json`）与 **计划**（`interview_plans.plan_json`、版本历史）**均已持久化**。
- 因此面试记录里**可以有「未开始正式面试」**：计划已生成/已锁定，但尚未 `activate`。

#### 会话状态（后端 `status`）

```text
planning → plan_ready → plan_confirmed → active → evaluating → completed
```

| 候选人可见 | 后端 status | 含义 |
|---|---|---|
| 准备中 / 待确认计划 | `planning`、`plan_ready` | 计划生成中或待预览/确认（少见滞留，一般仍在计划页） |
| **未开始** | `plan_confirmed` | 计划已锁定，**尚未** `POST /activate` |
| **面试中** | `active` | 已激活，可继续对话；45 分钟倒计时进行中 |
| **评估中** | `evaluating`（`finish_reason` ≠ `stale_deadline_reached`） | 面试已结束（手动/答完），evaluate 进行中或报告已可查看 |
| **待评估** | `evaluating`（`finish_reason` = `stale_deadline_reached`）；或 stale `active` | 倒计时在后台结束，**尚未**触发生成报告 |
| **已结束** | `completed` | 评估已写入 `evaluation_json` |

列表对外展示 **五类标签**（见下节 UI 契约）；`planning` / `plan_ready` 在列表中合并展示为 **未开始**（或副文案区分「待确认计划」），实现仍以 `status` + `finish_reason` 驱动跳转。

#### 面试记录列表 UI 契约（定稿）

侧边栏「面试记录」→ `/interviews` 列表。每条会话展示：**标题、岗位、状态标签、更新时间**；卡片右下角 **主按钮**（点击卡片与点击按钮行为一致，除非另做整卡跳转）。

| 列表标签 | 判定条件（优先级从高到低） | 右下角按钮 | 跳转页面 |
|---|---|---|---|
| **未开始** | `plan_confirmed`；或 `planning` / `plan_ready`（计划未锁定/待确认，合并展示） | **开始面试** | `/interviews/:id/live`（`plan_ready` 未 confirm 时也可先 `/plan` 完成确认后再 live） |
| **面试中** | `active` **且** 剩余时间 **> 0** | **继续面试** | `/interviews/:id/live` |
| **评估中** | `evaluating` **且** `finish_reason` ≠ `stale_deadline_reached` | **查看评估报告** | `/interviews/:id/evaluation` |
| **待评估** | `evaluating` **且** `finish_reason` = `stale_deadline_reached`；或 `active` **且** 剩余时间 **≤ 0**（stale active，见边界 B4） | **生成评估报告** | `/interviews/:id/evaluation` |
| **已结束** | `completed`（已有 `evaluation_json`） | **查看评估报告** | `/interviews/:id/evaluation` |

**评估中 vs 待评估 vs 已结束（同一路由、不同含义）：**

- **评估中**：用户主动结束或答完，`finish_interview` 已写入 `finish_reason`（如 `user_requested`）；evaluate 可能进行中或已完成；进入评估页可查看/等待报告。
- **待评估**：倒计时在后台结束（`stale_deadline_reached`）或 stale `active` reconcile 后；报告**尚未生成**；进入评估页后触发 `POST /evaluate` 或展示 loading / 失败重试。
- **已结束**：报告**已落库**；进入评估页后直接 `GET /evaluation` 展示，无需再生成。
- 三者都进 **`/evaluation`**，不用 live，不用计划页。

**边界 B4（提前离开 live、倒计时在后台走完）：**

- 业务上：时间已到，**不可再答题**。
- 列表标签：**待评估**（不得显示「面试中」）。
- 按钮：**生成评估报告** → `/evaluation`。
- 后端：列表或进入评估前须将 stale `active` **reconcile** 为 `evaluating`（等价 `finish`，reason 如 `deadline_reached`），再允许 evaluate。

**边界摘要：**

| 编号 | 场景 | 列表标签 | 按钮 | 跳转 |
|---|---|---|---|---|
| A | 计划已锁定，从未 activate | 未开始 | 开始面试 | live |
| B | active 且时间未到 | 面试中 | 继续面试 | live |
| C | 手动结束 / 答完 / live 页自动 finish | 评估中 | 查看评估报告 | evaluation |
| D | 离开 live 后倒计时结束（stale active） | 待评估 | 生成评估报告 | evaluation（先 reconcile，`finish_reason=stale_deadline_reached`） |
| E | evaluate 成功 | 已结束 | 查看评估报告 | evaluation |
| F | evaluate 失败仍 evaluating | 待评估 | 生成评估报告 | evaluation（重试） |

**与结束 live 页 UX（定稿）：**

- 用户点「结束面试」或到时自动 finish 后：**全屏遮罩**文案「正在生成评估报告，请稍后去面试记录页查看」。
- 后台触发 `POST /evaluate`（失败可在记录页重试）。
- **3 秒后**自动跳转 **`/interviews`**（面试记录页），**不再**直接跳 `/evaluation`。
- **面试记录页**对 `GET /api/interviews` **每 10 秒轮询**，以便及时从「评估中/待评估」变为「已结束」。

**面试记录是主路径**：用户离开后再回来，从列表按上表进入 live 或 evaluation。

#### 从面试记录点击（后端 status 映射，实现参考）

**判定顺序：先映射列表标签（含 active 是否过期），再跳转。**

| 后端 status | 附加条件 | 列表标签 | 跳转 |
|---|---|---|---|
| `planning` / `plan_ready` | — | 未开始 | `/plan` 或 `/live`（见 UI 表） |
| `plan_confirmed` | — | 未开始 | `/live` |
| `active` | 剩余时间 > 0 | 面试中 | `/live` |
| `active` | 剩余时间 ≤ 0 | 待评估 | reconcile → `/evaluation` |
| `evaluating` | `finish_reason` = `stale_deadline_reached` | 待评估 | `/evaluation` |
| `evaluating` | 其他 `finish_reason` | 评估中 | `/evaluation` |
| `completed` | — | 已结束 | `/evaluation` |

**状态流转校正（避免误解）：**

- **不是**「面试中 + 倒计时结束 → 仍在 active 里直接看报告」。
- **而是**：正式结束 → **`evaluating`** → evaluate → **`completed`**；stale `active` 在记录入口按 **待评估** 处理并 reconcile。

#### 实现清单

- 替换 `/interviews` 占位页为 V2 **会话列表**（对接 `GET /api/interviews`）。
- 列表项按 **「面试记录列表 UI 契约（定稿）」** 渲染五类标签与右下角按钮。
- 列表 API 返回：`status`、计算后的 `remaining_seconds`（或 `is_past_deadline`）、`has_evaluation`、标题、岗位、更新时间；过滤 legacy V1。
- stale `active`（剩余 ≤ 0）：列表标 **待评估**；列表请求时 **reconcile → evaluating**。
- 侧边栏「面试记录 · 尚未开放」改为可用入口。
- 面试记录页 **10s 轮询** 列表 API；`finish_reason` 写入 `workflow_state` 供列表区分 **评估中** / **待评估**。

不实现：

- 跨场次能力趋势、练前 HITL（07 暂缓/延期项）。
- 列表内无限重新评估。

前端验证：

- 五类标签与按钮文案与 UI 契约一致（未开始/面试中/评估中/待评估/已结束）。
- 手动结束后再从「面试记录」→ **评估中** → 评估页查看报告；stale 倒计时结束 → **待评估** → 生成报告。
- **已结束** 条目 → **查看评估报告** → 直接展示报告。
- 提前离开 live、倒计时结束后列表为 **待评估**，不得显示 **面试中**。
- `evaluating` 进入评估页时，生成中/失败可重试。

完成条件：

- **面试记录 → 评估** 成为与「结束页自动跳转」并列的主路径。
- 03 文档中「列表页尚未开放」项在 06 本补全后关闭。

### 小步 2：Evaluation Agent 与能力评分

实现：

- 接入 Evaluation Agent。
- 按能力输出评分、置信度和证据引用。
- 后端校验证据引用和分数。
- 使用确定性规则聚合总体分数。

前端验证：

- 每项能力可以展开查看证据。
- 未验证能力不显示低分。

后端验证：

- 不存在无证据高分或低分。
- 总体分数不直接采用模型自由输出。

完成条件：

- 证据驱动能力评估可用。

### 小步 3：JD 匹配分析

实现：

- 有 JD（`configuration.jd_text` 非空）时，从已锁定计划中 `source_refs` 含 `jd:` 的主题抽取本场对齐要点，结合 competency 与 05 证据分为已验证且符合、已验证但存在风险、尚未验证三档。
- 无 JD 时 `jd_match: null`，不显示空 JD 模块。
- 计划未标注 `jd:` 主题时仍返回 `jd_match`，`requirement_count = 0` 并给出说明摘要。

前端验证：

- 有无 JD 报告结构正确。
- 模块标题为「本场 JD 要点验证」，checklist 展示三档状态。
- 未验证要求不展示为不符合。

完成条件：

- JD 匹配表达准确，且范围限定为本场计划对齐要点。

### 小步 4：逐题复盘

实现：

- 按主题生成考察目的、有效信息、遗漏和回答组织建议。
- 引用相关问答和证据。

前端验证：

- 可以逐主题展开复盘。
- 不生成冗长标准答案。

完成条件：

- 候选人能够知道每个主题如何改进。

### 小步 5：练习建议与再次练习

实现：

- 将薄弱项转为可操作练习建议。
- 支持从报告带着重点方向创建下一次配置。

不实现：

- 自动开始新面试。

前端验证：

- 点击练习建议进入专题 02 配置页，并预填重点方向。

完成条件：

- 面试后到再次练习形成闭环。

> **跨场次能力趋势、练前 HITL 推荐** 见 [07 跨场次学习档案](./07-cross-session-learning.md)。**与上一场对比**（07 小步 1–2）已在评估页接入；不阻塞 06 首期验收。

## 9. 测试与验收

- 评估失败可重试，面试数据不丢失。
- 用户可从 **面试记录列表** 进入 `evaluating` / `completed` 会话的评估页；标签与按钮符合 UI 契约（小步 1 补全）。
- 每项评分可追溯到 05 evidence 或 plan 主题（§4.2）。
- `competencies` 与 plan 主题 id / dimension 对齐，无自造能力维度表。
- 未验证项不会被判低分。
- 校招和社招评分重点有差异。
- 有 JD 和无 JD 报告结构正确；有 JD 时 JD 模块范围为本场 plan `jd:` 对齐要点，非 JD 全文逐条解析。
- 逐题复盘引用真实 quote，且与对应 `topic_id` 一致。
- 可以从薄弱项发起下一次配置（本场）；跨场练前预填见 **07**（暂缓）。
- 06 首期验收不要求 07 全部完成；**07 已交付的跨场对比**不得影响本场评分主路径。
- **评估页**：已落库报告进入即展示；不因 refetch 反复出现全页 loading。
- **评分校准**：负面为主、无正向证据的 `partially_verified` 不得虚高至 40 分并配「有亮点」类标签。
- 新版评估链路稳定，旧教学版评估不再作为兼容目标。

## 10. 质量、安全与可观测

- 不在普通日志记录完整问答和完整评估证据原文。
- 记录评估版本、模型、耗时、覆盖率、证据数量、校验失败和降级情况。
- Evaluation Agent 只能评价已提供证据，不能补写候选人经历。
- 模型失败时可生成规则版最小报告，并明确置信度较低。
- 评估 Prompt 将候选人回答、JD 和知识库内容视为不可信输入。
- 真实 LLM 路径是评估质量验收标准；LLM 失败时可生成规则版最小报告并标注低置信度，**不使用 mock 模式**。

## 11. 停止条件

- 总体评分仍主要按回答长度计算。
- 无证据也能获得确定高分或低分。
- 未验证项被展示为不符合。
- 评估结果无法追溯到 05 工作记忆或 plan 主题。
- 报告能力维度与 `confirmed_plan.topics` 不一致或存在 plan 外自造维度。
- 历史表现影响当前评分（07 亦须遵守：本场 evaluate 不读档案做打分）。

## 12. 给 AI 的执行指令

```text
阅读 V2/ROADMAP.md、03-planning-and-human-in-the-loop.md、05-context-memory-evidence.md 和本文件。
一次只实现一个小步。
先完成最小评估页面，再完成面试记录入口（小步 1 补全），再实现证据评分、JD 匹配和练习闭环。
competencies 必须与 confirmed_plan.topics 对齐；评分主路径消费 05 evidence_by_topic，禁止另建与 plan 平行的维度体系。
不要修改证据提取或动态面试专题文档。
```

## 13. 实施记录

- **06 专题首期交付完成**（2026-06-11）：小步 1–5、小步 1 补全、评估页 UX、覆盖提示、评分校准、加载态修复均已落地；评估页「与上一场对比」消费 07 `learning-context`（07 小步 1–2）；练前 HITL 仍属 07 暂缓项。
- 2026-06-09：**小步 1** — 规则版最小评估闭环。
  - 后端：`POST /api/interviews/{session_id}/evaluate`、`GET /evaluation`（V2）；`InterviewEvaluationService` + `interview_evaluation/context.py` + `interview_evaluation/minimal_report.py`；状态 `evaluating → completed`；写入 `evaluation_json`。
  - 前端：`/interviews/:sessionId/evaluation` 评估页；结束面试遮罩 + 3s 跳面试记录页；展示摘要、覆盖、优势、**风险与未验证项分栏**。
  - 测试：`test_interview_evaluation_step1.py`、`test_interview_evaluation_step1_unit.py`。
  - 未做：正式能力评分、JD 匹配、逐题复盘（留小步 2–4）；**面试记录列表**（小步 1 补全进行中）。
- 2026-06-09：**小步 4 & 5** — 逐题复盘 + 练习建议闭环。
  - 后端：`question_reviews.py` 按 plan 主题输出考察目的、有效信息、遗漏/风险、组织建议、练习点、原话引用；`practice_recommendations.py` 从薄弱项生成重点方向并映射到 02 `focus_topics`。
  - 前端：评估页「逐题复盘」「下一步练习建议」；点击练习建议跳转 `/interviews/new` 并预填重点方向。
  - 测试：`test_interview_evaluation_step4_step5_unit.py`。
- 2026-06-09：**小步 3** — JD 匹配分析（本场要点验证）。
  - 后端：`interview_evaluation/jd_match.py`；门控为 `configuration.jd_text` 非空；要点**仅**从 plan 主题 `source_refs` 的 `jd:` / `jd：` 项抽取（不对 JD 原文逐条解析）；按 competency + 05 证据分为 **verified_aligned / verified_with_risk / unverified**；无 JD 时 `jd_match: null`；有计划 JD 文本但无 `jd:` 主题时 `requirement_count = 0`。
  - 前端：评估页「本场 JD 要点验证」checklist 模块（仅有 JD 时展示）；统计已验证/有风险/尚未验证；未验证不写「不符合」。
  - 测试：`test_interview_evaluation_step3_unit.py`。
- 2026-06-09：**小步 2** — 证据驱动能力评分 + Evaluation Agent 文案增强。
  - 后端：`interview_evaluation/competencies.py` 确定性 status/score/confidence；`aggregate.py` 综合分聚合；`report.py` 组装报告；`agent/interview_evaluation` LLM 摘要增强（失败降级 `evidence_rule`）。
  - 报告新增 `competencies[]`、`overall_score`；`unverified` 无分数；证据引用链到 05 quote。
  - 前端：评估页能力维度卡片，可展开查看证据引用；未验证不显示低分。
  - 测试：`test_interview_evaluation_step2_unit.py`；step1 集成测试兼容新 source。
- 2026-06-09：**小步 1 补全** — V2 面试记录列表、`GET /api/interviews`、stale active reconcile；live 结束遮罩 + 3s 跳记录页 + 后台 evaluate；记录页 5s 轮询。
- 2026-06-09：**面试记录 UI 契约定稿** — 四类标签（未开始 / 面试中 / 待评估 / 已结束）与右下角按钮（开始面试 / 继续面试 / 生成评估报告 / 查看评估报告）；待评估与已结束均跳转 `/evaluation`；stale `active`（离页后倒计时结束）标待评估并 reconcile。
- 2026-06-09：**结束 live UX 定稿** — 遮罩「正在生成评估报告…」→ 3s 后 `/interviews`；不再结束即跳 evaluation。
- 2026-06-11：**评估页展示与覆盖提示修正**
  - **回答依据**：能力维度展开后展示该主题下**全部 Q&A 轮次**（后端 `answer_rounds` / `build_competency_answer_rounds`）；去掉「亮点/记录/待加强」标签，仅保留问答原文。
  - **维度评价**：评价区块背景色随 `verified` / `partially_verified` / `unverified` 状态标签变化。
  - **综合得分圆环**：按分数区间着色（≥80 绿、≥60 蓝、<60 红）；**部分评分不再将圆环置灰**（`SCORE_RING_TIER` / `evaluationScorePresentation.ts`）。
  - **覆盖提示 bug**：「你聊到 X 个」原用 `completed_topic_ids` 计数，手动结束当前主题未写入导致「聊到 0、已评 1」矛盾。修复：`finish_interview` 将 `current_topic_id` 并入 `completed_topic_ids`；新增 `discussed_topic_count`（`count_discussed_topics`）；前端优先用实时计算的 `coverage_note`，旧报告刷新即正确。
  - 测试：`test_interview_evaluation_aggregate.py`、`test_interview_evaluation_evidence_references.py`。
- 2026-06-11：**面试记录状态细分（评估中 vs 待评估）**
  - 列表标签由四类扩为五类：**评估中**（`evaluating` 且非 `stale_deadline_reached`）→ 按钮「查看评估报告」；**待评估**（stale 倒计时 / `finish_reason=stale_deadline_reached`）→ 「生成评估报告」。
  - `finish_reason` 持久化到 `workflow_state`；列表 reconcile stale `active` 时使用 `stale_deadline_reached`。
  - 轮询间隔 **5s → 10s**（`useInterviewSessionList.ts`）。
- 2026-06-11：**进入对话与结束流程**
  - **计划页**：确认计划后先 `POST /activate`，再跳 `/live`（无 `autostart` 参数）；加载文案「正在进入…」。
  - **对话页**：`evaluating` 状态**不再自动跳转**评估页；结束流程 `beginPostFinishFlow` 遮罩 3s 后去 `/interviews`；仅 `completed` 且非结束流程时可能自动进评估页。
- 2026-06-11：**前端路由与请求**
  - 路由切换用 `useRouteRemountKey`（`pathname+search`）remount，避免同页重复挂载 stale 数据。
  - 移除 `refetchOnMount: 'always'` 与开发环境 `StrictMode`，消除切换路由时同一接口双请求。
- 2026-06-11：**评分校准收紧**
  - `partially_verified` 取消 2 分地板；无正向证据时从 1 分起算，负面证据惩罚加重（`competencies.py`）。
  - 按分数分档标签：≤2「明显不足」、3「仍有明显缺口」、≥4「有亮点待加强」（`presentation.py` + 前端 `resolveCompetencyStatusLabel`）。
  - 低分维度 UI 改为红色系（`low` tone）；覆盖侧栏低分标「未达标」。
  - 测试：`test_interview_evaluation_scoring_calibration.py`。
- 2026-06-11：**评估页 loading 修复**
  - **现象**：记录列表已显示评估完成、GET `/evaluation` 有完整数据，页面仍一直「正在生成面试反馈」。
  - **根因**：`isGenerating` 误用 `isFetching`，后台 refetch 时遮挡已加载报告；且未 GET 优先，可能在 `evaluating` 时重复 POST。
  - **修复**：`useInterviewEvaluationReport` 先 GET 再按需 POST；全页 loading 改为 `isPending && !report`；`staleTime: 30s`。
- 2026-06-12：**文档与 commit 对齐** — 移除 Evaluation RAG / 08 编号；跨场对比改为消费 07（小步 1–2 已交付）；明确 06 仅展示、07 拥有聚合逻辑。
