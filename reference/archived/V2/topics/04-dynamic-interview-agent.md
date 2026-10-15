# 动态面试 Agent

## 1. 文档状态

- 状态：**已完成**（小步 1–6；Evidence 段已由专题 **05** 替换 stub）
- 对应路线图：阶段 6
- 核心 Agent：Interview Agent
- 前置专题：03 面试计划与人工介入

## 2. 改造目标

基于已锁定计划完成一场有明确终点的动态模拟面试。Interview Agent 可以根据回答追问、切题和调整难度，但不能突破代码定义的时间、轮数和状态边界。

**计划—对话必须契合**：对话只能执行已锁定计划中的考察方向与抓手，不得另起一套题单或无关追问；动态性体现在「怎么追、何时切题、如何升降深度」，而不是「考什么方向」与计划脱节。

## 3. 本专题范围

### 负责

- Interview Agent
- 计划—对话一致性（消费已锁定 plan_json，见 §4.1）
- Observe、Decide、Act 面试循环（**小步 6 起由 LangGraph StateGraph 编排**）
- 决策与自然语言生成分离
- Interview Reply 图：`state` / `graph` / `nodes` / `routing`（见 §6.5）
- 允许动作集合
- 主题进度、追问、切题和结束
- 45 分钟与回答轮数控制
- 最小运行记忆：消息持久化、每主题线程、`topic_summaries`、运行状态计数（见 §4.3）
- 面试页面、SSE 和相关 API

### 不负责

- 完整证据提取和复杂工作记忆（见 §4.3，由专题 05 增量接入）
- 最终能力评分

## 4. 依赖契约

- 消费专题 03 输出的不可变已确认计划。
- 首期使用本专题维护的最小主题摘要；专题 05 完成后可消费结构化工作记忆。
- 向专题 05 提供消息、主题、动作轨迹和运行状态。
- 向专题 06 提供完整问答、面试完成状态和主题覆盖情况。

### 4.1 计划—对话一致性（硬要求）

- 对话**只能**消费 `confirmed_plan_id` 对应的不可变 `plan_json`，不得重新生成主题清单或替换主考察方向。
- 每个主题的**首问**必须来自该主题 `opening_question`；Act 层**允许口语化改写**（更自然、更短），但**不得改变考察 intent**（`objective`、`dimension`、`focus_points` 指向的能力点不变）。
- Decide 必须对照当前主题的 `expected_signals`、`focus_points`、`probe_strategies` 判断「还缺什么」，并在 `reason` / `expected_information` 中可追溯到计划字段。
- Act 生成的追问必须可追溯到：**计划字段 + 合法 action + 候选人实际回答**；禁止与当前主题无关的通用八股题。
- Observe 上下文须与 Planning **同源**：同一份简历结构化结果、`jd_text`、`interview_type`、岗位/难度配置（可截断，不可换一套输入）。
- 切题时使用下一主题的 `opening_question`（同样允许口语化）；切换前将当前主题写入 `topic_summaries`，再更新 `current_topic_id`。
- **禁止**在 activate 或 reply 时重新调用 Planning Agent 或等价「现场出题」逻辑。

**一致性验收标准**：任意一轮 assistant 消息（含首问与追问），应能指出其对应的 `topic_id`，以及计划中的哪条 `expected_signal` / `probe_strategy` / `opening_question` 意图（追问允许 action 映射，不要求字面一致）。

### 4.2 消费专题 03 的 plan_json

每个主题至少读取：

- `id`、`name`、`dimension`、`required`、`objective`
- `opening_question`（首问来源；不对用户提前展示）
- `focus_points`、`expected_signals`、`probe_strategies`（Decide / Act 参考 hint，**非固定脚本**）
- `evaluation_criteria`（仅内部，不进入候选人可见话术）

配置与上下文此外读取：

- `interview_type`（校招 / 社招 Prompt 分叉）
- 创建会话时的简历结构化字段、`jd_text`（Observe 注入，需长度截断）

### 4.3 与专题 05 的记忆边界（不合并、不重复开发）

| 能力 | 专题 04（本专题） | 专题 05 |
|---|---|---|
| 当前主题最近 Q&A | ✅ 持久化于 `messages`，Observe 直接读取 | 不重复实现 |
| 切题后的 `topic_summaries` | ✅ **规则/轻量 LLM 压缩**（1–3 句：本主题考什么、候选人说了什么） | 05 升级为**证据化摘要**（含 claims / 覆盖度） |
| 结构化工作记忆（claims / evidence / risks） | ❌ 不实现 | ✅ Evidence Extraction + 工作记忆 Schema |
| 缺失信息驱动 Decide | ✅ 首期对照 `expected_signals` + 最新回答 | 05 改为消费结构化 `gaps` / 证据强度 |
| 避免重复追问已验证内容 | ❌ 首期不做 | ✅ 05 小步 3 |

**原则**：04 只实现「能跑通动态面试的最小记忆」——**消息 + 简单主题摘要 + 运行状态计数器**；05 在 04 已落库的 messages / 轨迹之上**增量接入** Evidence 与工作记忆，通过 `get_interview_memory_context()` 注入 Observe/Decide 图节点，**不重写**边界与 plan 契约。04 必须在 05 未就绪时可独立运行（降级输入 = 计划字段 + 当前主题消息 + `topic_summaries`）。

**与 05 的图节点边界（小步 6 起）**：

| 节点 | 归属 | 说明 |
|---|---|---|
| `ingest_answer` / `build_observe` / `enforce_boundaries` / `decide` / `act_*` / `finalize_*` | **04 小步 6** | 等价迁移现有 Handler |
| `extract_evidence` / `merge_working_memory` | **05** | 04 小步 6 仅留 **stub 直通**节点占位，不实现业务 |

### 4.4 旧能力处理边界

- 直接保留：LLM Factory、模型配置、错误处理、日志、SSE 格式化和流式输出等通用基础能力；`decide.py` / `act.py` / `prompts.py` / `boundaries.py` / `actions.py` 节点内复用。
- 允许抽取：不包含旧固定追问和固定题序规则的通用流式、结构化决策校验或持久化辅助能力。
- **LangGraph（小步 6）**：V2 面试 **Reply 每轮** 使用 `StateGraph` 编排；Planning（03）、Evaluation（06）**不在本小步改图**。V1 `backend/app/agent/workflow.py` 的 `interview_graph` 标记为 legacy，V2 主路径不得回退调用。
- 允许借鉴：`niumian-langgraph` 的**每主题对话线程**、**对话历史格式化**、CV/校招追问语气与反越狱话术；**LangGraph 用法**借鉴「State + Node + conditional_edges」，**不借鉴**其 `NEXT_QUESTION` 切题与单 Prompt 决策+话术。
- 禁止照搬：niumian 固定 `question_list` 题号推进、`<!-- NEXT_QUESTION -->` 切题、单 Prompt 决策+话术合一、Prompt 内轮数边界、`question_setter` 题单形态。
- 禁止混用：不得让 Decide/Act 回退为 niumian 式「单 Prompt 输出追问或切题标记」；切题与结束以 **boundaries 节点 + 条件边** 强制，不交给 LLM。
- 禁止混用：LangGraph **节点内不得**直接调用 `Store`、写 HTTP 响应或 SSE；持久化留在 `InterviewAgentService`（invoke 前读 DB、invoke 后写 DB）。
- 替换重构：小步 6 完成后，`InterviewReplyHandler.process()` 瘦身为 `interview_reply_graph.invoke()` 薄封装；允许删除 Handler 内联分支逻辑，迁至 `agent/interview/nodes/`。
- 允许破坏：旧 `InterviewService`、`CvInterviewWorkflow` 的回答与追问节点、旧 `interview_sessions` 和 `messages` 表可以被替换。
- 验证要求：新版开始、回答、结束、SSE 和会话恢复流程稳定；计划—对话一致性可测试（见 §9）。

## 5. 产品规则

### 4.1 固定边界

| 项目 | 限制 |
|---|---:|
| 面试截止时间 | 激活后 45 分钟 |
| 收尾触发 | 剩余 5 分钟 |
| 最大回答轮数 | 12 |
| 单主题最大回答轮数 | 3 |
| 单主题最大追问数 | 2 |
| 连续追问同一缺失信息 | 最多 1 次 |

### 4.2 允许动作

```text
probe_detail
probe_ownership
probe_metric
probe_tradeoff
probe_risk
increase_difficulty
decrease_difficulty
next_topic
finish
```

### 4.3 动作优先级

后端先计算硬规则，再执行 Agent 决策：

1. 已完成或未激活：拒绝回答。
2. 达到截止时间或最大轮数：强制 `finish`。
3. 进入收尾区且必须主题已覆盖：优先 `finish`。
4. 当前主题达到轮数或追问上限：强制 `next_topic`。
5. Agent 从剩余合法动作中决策。

### 4.4 候选人体验

面试开始前提示：

> 本次面试预计 45 分钟，将覆盖约 4 至 5 个能力方向。系统会根据回答情况进行追问，单个方向最多追问两次。

面试中展示：

- 当前主题
- 已完成主题数 / 总主题数
- 当前状态：主题问题或深入追问
- 预计剩余时间
- 主动结束按钮

不显示固定题号和内部动作名称。

## 6. Interview Agent 设计

### 5.1 Observe

首期读取：

- 已锁定 `plan_json` 全文及**当前主题完整条目**（见 §4.2）
- 与 Planning 同源的简历结构化字段、`jd_text`（截断）、`interview_type`、岗位配置
- 当前主题最近消息（每主题独立线程，不混用其他主题全文）
- `topic_summaries` 中已完成主题的简单摘要
- 当前轮数、追问计数、剩余时间、最新回答

专题 05 完成后，经统一上下文接口追加：结构化工作记忆、缺失信息（见 §4.3）。**05 未就绪时 04 仍用上述降级输入运行**。

### 5.2 Decide

输入除 Observe 字段外，必须包含当前主题的 `expected_signals`、`probe_strategies`、`dimension`、`focus_points`。

结构化输出：

```json
{
  "action": "probe_tradeoff",
  "target_topic_id": "topic-2",
  "reason": "候选人说明了最终方案，但没有说明备选方案",
  "expected_information": ["备选方案", "选择依据", "代价"],
  "should_change_topic": false
}
```

决策输出只决定做什么，不包含直接说给候选人的完整问题。`reason` 与 `expected_information` 须能对应计划中的考察意图（`expected_signals` / `focus_points`），不得与当前主题 `objective` 无关。

| action | 主要意图（须对齐当前主题 plan 字段） |
|---|---|
| `probe_ownership` | 个人贡献、职责边界、项目真实性 |
| `probe_metric` | 结果指标、验证方式 |
| `probe_tradeoff` | 方案取舍、备选方案与约束 |
| `probe_risk` | 风险、故障、质量与代价 |
| `probe_detail` | 实现细节、实践深度 |
| `increase_difficulty` / `decrease_difficulty` | 在计划考察范围内升降深度 |

### 5.3 Act

Question Generation 根据合法决策生成自然话术：

```json
{
  "message": "当时还考虑过哪些方案？最终选择当前方案时，最主要的约束是什么？"
}
```

生成失败时使用基于 **action 类型 + 当前主题 `probe_strategies` 首条** 的本地模板（禁止全局通用八股库）。

Act（Question Generation）要求：

1. 首问与切题后的开场：以该主题 `opening_question` 为语义来源，**允许口语化改写**（更短、更自然），不得偏离 `objective` / `dimension`。
2. 追问：一次只问一个问题，约 40–120 字口语化中文。
3. 必须基于候选人**实际**回答延伸；禁止虚构「你刚才提到…」等未出现的内容。
4. 可结合 JD / 简历项目设场景，但不得编造候选人未提及的经历。
5. 校招（`campus`）语气更温和、循序渐进；社招（`experienced`）更直接、偏深度验证（可参考 niumian 校招/社招 Prompt 风格，**须重写为计划驱动**，禁止整段照搬）。
6. 候选人要求解释概念、探测 prompt、索要标准答案时：拒绝并引导回到当前主题问题（不展开教学、不透露评分或流程）。
7. 输入须包含：合法 `action`、Decide 的 `reason` / `expected_information`、当前主题 plan 条目、当前主题最近对话、Observe 上下文摘要。

真实 LLM 路径是动态追问质量和自然度的验收标准。LLM 失败时走**规则降级**（Decide，`build_rule_fallback_decision`）与**模板降级**（Act，`build_template_fallback_act_message`；Opening 退回 plan 原文），仅保证流程与结构合法，不模拟真实面试判断质量。

### 5.4 借鉴 niumian 对话 Agent 的边界

niumian `interview_ask_agent`（`type=cv/campus`）是**固定题单 + 单 Prompt 动态追问**。本专题**只借鉴其 Prompt 工程与每主题对话线程**，**不借鉴**产品形态与控制方式。

| 借鉴 | 04 映射 |
|---|---|
| 每题独立 `messages` | 当前主题消息线程 + `messages.meta.topic_id` |
| 简历 + JD + 题 metadata 进 Prompt | Observe + Act；metadata 来自 **03 plan 主题** |
| 预设追问作参考、按对话灵活调整 | `probe_strategies` 作 hint，非脚本 |
| 按回答质量升降深度 | Decide → `increase/decrease_difficulty` 或不同 `probe_*` |
| 自然过渡、一次一问、禁止虚构 | Act Prompt 硬约束 |
| 校招 / 社招不同语气 | `interview_type` 分叉 Act |
| 反越狱与角色边界 | Act + §10 |

| 不借鉴 | 原因 |
|---|---|
| `question_list` + 题号推进 | V2 是主题计划 |
| `<!-- NEXT_QUESTION -->` | 切题由代码 `next_topic` 强制 |
| Prompt 内「最多 3 轮」 | 由运行状态计数器保证 |
| 决策与话术同一 Prompt | 违反 Decide/Act 分离 |
| niumian 整图照搬 | V2 边界在代码节点，非 Prompt 标记 |

### 5.5 LangGraph 编排架构（小步 6）

**范围**：仅 **每轮 `reply`**（候选人提交一次回答 → 生成一条 assistant 消息）。`activate` 首问、`finish` 主动结束仍由 Service + `opening.py` / `transitions.py` 处理，不纳入 Reply 图。

#### 5.5.1 分层

```text
InterviewAgentService（API / 持久化 / SSE / reply_in_progress）
  ├─ 读：plan_json、messages、workflow_state
  ├─ interview_reply_graph.invoke(initial_state, config)
  └─ 写：user/assistant messages、workflow_state、status

agent/interview/
  ├─ state.py          InterviewReplyState (TypedDict)
  ├─ graph.py          StateGraph compile
  ├─ routing.py        conditional_edges 路由函数
  └─ nodes/            纯函数节点（无 Store / 无 HTTP）
```

**跨轮真相源**：DB `workflow_state`（`runtime_state` 字段）。**单轮图内状态**：`InterviewReplyState`。每轮 invoke 结束将 `runtime_state` 与 outcome 写回 DB。

#### 5.5.2 图拓扑（小步 6 等价迁移）

```text
START
  → ingest_answer           # 轮次+1；筛 current topic_messages
  → build_observe           # build_observe_context + get_interview_memory_context（05 前为空）
  → enforce_boundaries      # evaluate_forced_action → state.boundary

  ── route_after_boundary ──
     finish       → finalize_forced_finish → END
     next_topic   → finalize_advance        → END
     continue     → pass_through_evidence     # 05 占位 stub，原样透传

  → decide                  # InterviewDecideAgent + normalize_decision
  ── route_after_decide ──
     probe          → act_probe → END
     repeat_blocked → finalize_advance → END
     advance        → finalize_advance → END

finalize_advance / finalize_forced_finish / act_probe：
  # 等价现有 _handle_advance / _handle_forced_finish / _handle_probe
  # 写入 topic_summaries、completed_topic_ids、assistant_*、next_status
```

**路由键**由节点写入 `state["route"]` 或 `state["boundary"]` / `state["decision"]`，**路由函数只读 state**，不在边函数里调 LLM。

#### 5.5.3 InterviewReplyState（最小字段）

```python
# 输入（Service 注入）
trace_id, plan_json, configuration, resume,
runtime_state, current_topic, all_messages, latest_answer

# 中间态
topic_messages, observe_context, memory_context,
boundary, decision

# 输出（Service 消费）
assistant_content, assistant_kind, assistant_meta,
next_status, runtime_state  # 已更新的运行状态
```

列表 merge（05 起 `working_memory`）再引入 `Annotated[..., reducer]`；小步 6 不必提前引入。

#### 5.5.4 节点与现有模块映射

| 图节点 | 现有实现 | 节点类型 |
|---|---|---|
| `ingest_answer` | `ReplyHandler.process` 开头 | 确定性 |
| `build_observe` | `context.build_observe_context` | 确定性 |
| `enforce_boundaries` | `boundaries.evaluate_forced_action` | 确定性 |
| `pass_through_evidence` | （无） | 05 stub |
| `decide` | `InterviewDecideAgent` + `actions.normalize_decision` | LLM + 确定性 |
| `act_probe` | `InterviewActAgent` + probe 状态更新 | LLM |
| `finalize_advance` | `_handle_advance` | LLM（切题 Act）+ 确定性 |
| `finalize_forced_finish` | `_handle_forced_finish` | 确定性 |

#### 5.5.5 Checkpointer（小步 6 可选，非阻塞）

可使用 `SqliteSaver`，`configurable.thread_id = session_id`，用于**单轮内**多节点失败恢复（如 decide 成功、act 失败）。**不替代** DB `workflow_state` 跨轮持久化。首期验收不强制。

#### 5.5.6 推荐目录（小步 6 完成后）

```text
backend/app/agent/interview/
├── state.py
├── graph.py
├── routing.py
├── nodes/
│   ├── ingest.py
│   ├── observe.py
│   ├── boundaries.py
│   ├── extract_evidence.py   # 05 替换原 stub
│   ├── merge_working_memory.py
│   ├── decide_node.py
│   ├── act.py
│   └── finalize.py
├── decide.py               # LLM 客户端（节点调用）
├── act.py
├── prompts.py
├── opening.py
└── rule_fallback.py

backend/app/services/interview/
├── reply_handler.py        # 薄封装：invoke graph → ReplyOutcome
└── ...                     # boundaries / runtime_state 等保留
```

## 7. 数据、状态与 API

### 6.1 状态

```text
plan_confirmed -> active -> evaluating -> completed
```

本专题只负责到 `evaluating`。专题 06 完成前，可以生成最小完成摘要作为占位。

### 6.2 运行状态

至少保存：

```json
{
  "started_at": "",
  "deadline_at": "",
  "current_topic_id": "",
  "completed_topic_ids": [],
  "required_topic_ids": [],
  "interview_type": "",
  "answer_round": 0,
  "current_topic_round": 0,
  "current_topic_probe_count": 0,
  "last_probed_information": "",
  "topic_summaries": {},
  "last_action": ""
}
```

- `required_topic_ids`：来自 plan 中 `required=true` 的主题，用于收尾区「必考覆盖」判定。
- `last_probed_information`：实现「连续追问同一缺失信息最多 1 次」。
- `topic_summaries`：切题时写入简单摘要（首期 1–3 句）；05 完成后可升级为证据化摘要，**字段名保持不变**。

### 6.3 消息

建议使用新版 `messages` 表或等价消息存储，消息 `meta` 至少记录：

- `topic_id`
- `action`
- `trace_id`
- `is_follow_up`

### 6.4 API

```http
POST /api/interviews/{session_id}/activate
POST /api/interviews/{session_id}/reply/stream
POST /api/interviews/{session_id}/finish
GET  /api/interviews/{session_id}
```

- `activate`：仅 `plan_confirmed` 且 `confirmed_plan_id` 有效；扣减用户面试额度；首问来自当前主题 `opening_question`（可 Act 口语化）。
- 旧版 `POST /api/interviews/stream` 不得作为 V2 会话入口。

SSE 事件建议：

```text
session_state
message_start
delta
message_end
progress
done
error
```

## 8. 分步实施

### 小步 1：按计划顺序完成固定主题面试

实现：

- 激活已确认计划；加载 `confirmed_plan_id` 对应 `plan_json`。
- 按主题顺序提出开场问题（来自 `opening_question`，可口语化）。
- 每个主题回答一次后切到下一主题；切题前写入 `topic_summaries`。
- 保存消息（含 `meta.topic_id`）和运行状态。

不实现：

- 动态追问。
- 45 分钟和 12 轮边界。

前端验证：

- 可以开始、回答、切换主题和恢复会话。
- 显示主题进度而不是题号。

完成条件：

- 新版面试闭环可运行。
- 首问与计划 `opening_question` 语义一致（允许措辞口语化）。

### 小步 2：结构化决策和动态追问

实现：

- 增加 Decide 节点（输入含当前主题 plan 字段 + `expected_signals`）。
- 增加允许动作校验。
- 增加 Question Generation（Act；首问/切题允许口语化，追问须对齐 action 与 plan）。
- 首期使用 `topic_summaries`、当前主题最近消息和最新回答（不依赖 05 工作记忆）。

不实现：

- 复杂证据提取（属 05）。

前端验证：

- 模糊回答会触发追问。
- 充分回答会切题。

后端验证：

- 非法动作被拒绝或降级。
- 决策与话术输出分离。
- 追问可映射到当前主题的 `expected_signals` 或 `probe_strategies`（一致性抽查）。

完成条件：

- Agent 能够动态选择追问或切题，且对话不偏离计划考察方向。

### 小步 3：单主题边界

实现：

- 单主题最多追问 2 次。
- 单主题最多回答 3 轮。
- 连续追问同一信息最多一次。

前端验证：

- 无论回答如何，同一主题不会无限持续。

完成条件：

- 单主题硬边界由代码保证。

### 小步 4：整场时间和轮数边界

实现：

- 激活时记录截止时间。
- 最大回答 12 轮。
- 剩余 5 分钟进入收尾。
- 达到边界自动结束。

前端验证：

- 显示预计剩余时间。
- 达到最大轮数后自动结束。

后端验证：

- 修改模型输出也不能突破边界。

完成条件：

- 整场面试有可靠终点。

### 小步 5：主动结束、异常恢复和 SSE 完善

实现：

- 主动结束确认。
- 刷新后恢复。
- 重复提交和已完成回答保护。
- 流式错误事件和恢复提示。

前端验证：

- 主动结束后进入完成状态。
- 刷新后状态、消息和进度一致。

完成条件：

- 动态面试可稳定使用。

### 小步 6：Reply 链路 LangGraph 化（分两步）

**总目标**：编排从 `InterviewReplyHandler` 内联 if/else 迁至 LangGraph；**行为、API、测试与 §9 验收不变**；为 05 Evidence 节点预留图位。

---

#### 小步 6A：图骨架 + 单节点透传（先做）

**目标**：`InterviewAgentService → interview_reply_graph.invoke → ReplyOutcome` 通路打通；业务逻辑仍集中在 `process_legacy`，行为不变。

实现：

- 新增 `agent/interview/state.py`（`InterviewReplyState`）
- 新增 `agent/interview/graph.py`（`START → run_legacy_reply → END`）
- 新增 `agent/interview/nodes/run_legacy_reply.py`（调用 `InterviewReplyHandler.process_legacy`）
- `InterviewReplyHandler.process()` 改为组装 state、`invoke`、映射 `ReplyOutcome`
- 现有 `process` 主体更名为 `process_legacy`（供单节点调用）

不实现：

- 多节点拆分、`routing.py`、条件边
- `pass_through_evidence` stub
- 05 Evidence、Planning/Evaluation 图化

后端验证：

- `test_interview_agent_step1.py`、`step3.py`、`step4_step5.py` **全部通过**

完成条件：

- 每轮 reply 经 `interview_reply_graph.invoke`；API/SSE/前端无感知。

---

#### 小步 6B：节点拆分 + Evidence stub（6A 全绿后一次完成）

**目标**：将 `process_legacy` 拆为 §6.5 完整拓扑；Handler 仅薄封装。

实现：

- 新增 `routing.py` 与 `nodes/`（`ingest`、`observe`、`boundaries`、`decide_node`、`act`、`finalize`、`evidence_stub`）
- `enforce_boundaries` 为确定性节点；切题/结束走 **conditional_edges**
- `pass_through_evidence` stub：`continue` 分支上 decide 之前透传
- 删除 `process_legacy` 与 Handler 内联分支编排
- （可选）单节点单测、SqliteSaver checkpointer

不实现：

- 05 真实 Evidence Extraction / merge（属专题 05）
- 变更 `get_interview_memory_context` 契约或 plan 对齐规则

后端验证：

- §9.3 LangGraph 迁移项满足；`test_interview_agent_step*` 全绿

完成条件：

- V2 reply 主路径仅经拆分后的图；05 可替换 `pass_through_evidence` 为 `extract_evidence` → `merge_working_memory`。

## 9. 测试与验收

### 9.1 流程与边界

已实现自动化测试（`test_interview_agent_step1.py`、`step3.py`、`step4_step5.py`）：

- 只有已确认计划可以激活。
- 动态追问和切题均可触发。
- 非法动作无法执行（`normalize_decision` + 允许动作集合）。
- 单主题最多追问 2 次（`test_topic_probe_limit_advances`）。
- 单主题最多回答 3 轮（`test_topic_answer_round_limit_forces_advance`）。
- 连续追问同一缺失信息最多 1 次（`test_repeat_probe_blocked_advances_topic`）。
- 整场最多回答 12 轮（`test_max_answer_rounds_forces_finish`）。
- 达到截止时间会结束（`test_past_deadline_forces_finish`）。
- 剩余 5 分钟收尾区：必考覆盖后结束、未覆盖则切题（`test_wrap_up_zone_*`）。
- 用户可以主动结束（`test_user_finish_interview`）。
- 刷新后会话恢复（`GET /api/interviews/{id}` + 前端 `useLiveInterviewSession`）。
- 已完成会话不能继续回答（`test_evaluating_session_rejects_reply`）。
- 重复并发回复保护（`test_duplicate_reply_rejected`）。
- 新版面试行为稳定，旧固定追问流程不再作为兼容目标。

### 9.2 计划—对话一致性（必测）

- 激活后首条 assistant 消息须对应当前主题 `opening_question` 的考察 intent（允许口语化，禁止换成无关方向）。
- 切题后首问须来自下一主题 `opening_question`（同样允许口语化）。
- 每条追问须携带 `meta.topic_id`，且与 `current_topic_id` 一致。
- 抽样或自动化断言：Decide 的 `reason` / `expected_information` 与当前主题 plan 中至少一条 `expected_signal` 或 `focus_point` 语义相关。
- 抽样或自动化断言：Act 追问不得引入当前主题 plan 未覆盖的全新考察维度（如计划考「订单系统」，不得突然改考 unrelated 八股）。
- LLM 降级为本地模板时，模板须来自当前主题 `probe_strategies`，不得使用与 plan 无关的全局题库。
- 05 未接入时，面试仍可仅依赖 plan + messages + `topic_summaries` 完成全流程（无 Evidence 依赖）。

### 9.3 LangGraph 迁移（小步 6 必测）

**小步 6A（已完成）**：

- 每轮 reply 经 `interview_reply_graph.invoke` 完成。
- 图内仅 `run_legacy_reply` 单节点；行为与迁移前一致（同一套测试绿）。
- 图节点不访问 Store；消息与 `workflow_state` 仍由 Service 在 invoke 前后读写。

**小步 6B（已完成）**：

- Handler 无独立分支编排逻辑；`route_after_boundary` / `route_after_decide` 与迁移前 if/else 行为一致。
- `pass_through_evidence` 存在且为透传，Decide 输入与 6A 相同。
- 切题/结束不由 LLM 标记触发，仅 `enforce_boundaries` 与 `normalize_decision` 后路由。

### 9.4 对话质量（LLM 路径抽检，非 CI 硬门禁）

- 校招与社招在相同 action 下语气可区分（`interview_type` 分叉 Act）。
- 候选人索要标准答案或探测 prompt 时，Act 不泄露答案或系统规则。
- Act 不虚构候选人未提及的内容。

## 10. 质量、安全与可观测

- 普通日志不记录候选人完整回答。
- 记录 `trace_id`、当前主题、轮数、合法动作集合、最终动作、决策原因摘要、耗时和降级情况；小步 6 起可选记录 **graph 节点名 / route**（不含完整 state dump）。
- 候选人回答属于不可信输入，不能改变系统边界。
- 模型失败时使用规则决策（`rule_fallback`）和模板话术降级（`build_template_fallback_act_message`）。
- 后端 CI 通过 `FailingLLMClient` 模拟 LLM 失败，验证状态机与降级路径；不投入复杂规则模拟专业追问。
- 回复接口必须防止重复并发提交破坏状态。

## 11. 停止条件

- Agent 能突破硬边界。
- 状态无法持久化恢复。
- 决策与自然语言生成仍由同一个不可校验输出完成。
- 动态面试因 05 未就绪而无法运行（04 须在工作记忆为空时独立可跑）。
- 对话与已锁定计划考察方向系统性脱节，且无法通过 §9.2 一致性测试发现或修复。
- LangGraph 节点内直接持久化或调用 Planning Agent（§6.5.1）。
- 小步 6 迁移后现有 interview agent 自动化测试失败。

## 12. 给 AI 的执行指令

```text
阅读 V2/ROADMAP.md、03-planning-and-human-in-the-loop.md 和本文件。
若小步 1–5 已完成：
  - 小步 6A：仅图骨架 + run_legacy_reply 单节点透传（§8 小步 6A）；test_interview_agent_step* 全绿。
  - 小步 6B：节点拆分 + pass_through_evidence stub（§8 小步 6B、§6.5）；须 6A 已完成。
计划—对话一致性（§4.1）与硬边界（§5.3）在 6B 仍须满足；boundaries 必须是确定性图节点 + 条件边。
图内禁止 Store/HTTP/SSE；持久化留在 InterviewAgentService。
6A 不要拆节点；6B 不要实现 05 Evidence 业务。
不要改 Planning/Evaluation 图；不要改 get_interview_memory_context 契约。
```

## 13. 实施记录

- 2026-06-08：小步 1——`agent/interview` + `services/interview` 模块；`InterviewAgentService` 激活/固定主题流转；`messages.meta.topic_id`；`topic_summaries`；前端 `/interviews/:id/live`；§9.2 一致性测试（`FailingLLMClient` 降级路径）。
- 2026-06-08：小步 2——Decide/Act 分离（`decide.py` / `act.py` / `reply_handler.py`）；允许动作校验（`actions.py`）；模糊回答追问、充分回答切题；`get_interview_memory_context()` 05 接入点（04 返回空结构）；前端确认计划后直接进入正式面试。
- 2026-06-08：小步 3——`boundaries.py` 单主题边界（2 追问 / 3 轮 / 同信息 1 次）；`should_block_repeat_probe`；`test_interview_agent_step3.py`。
- 2026-06-08：小步 4——整场边界（12 轮、45 分钟截止、5 分钟收尾区 `is_wrap_up_zone`）；`serialization.py` 暴露 `remaining_seconds` / `phase` / `is_wrap_up_zone`。
- 2026-06-08：小步 5——`POST .../finish` 主动结束；`reply_in_progress` 并发保护；SSE `error` 事件；前端剩余时间 MM:SS 倒计时、归零自动 finish、结束确认弹窗、SSE 错误提示；`test_interview_agent_step4_step5.py`。
- 2026-06-08：Live 页 UI 重构（参照 `interview.png`）——顶部导航与 45 分钟说明、Meta 条（职位/进度/倒计时/结束按钮）、当前主题标签、面试官/候选人气泡与头像、候选人侧头像→名称→时间顺序。
- 2026-06-08：模拟流式（短期方案）——后端 `stream_interview_chunk_size` / `stream_interview_delay_ms` 分块 SSE；前端 `TypewriterStream` 打字机队列；Decide/Act 仍同步生成完整回复后再流式输出。
- 2026-06-08：移除 mock 模式——Decide/Act/Opening 仅 LLM 主路径 + 规则/模板降级；命名拆分 `rule_fallback.py` / `build_rule_fallback_*` / `build_template_fallback_*`；`conftest` 统一 `FailingLLMClient`。
- 2026-06-09：小步 6A——`agent/interview/state.py`、`graph.py`、`nodes/run_legacy_reply.py`；`InterviewReplyHandler.process()` 经 `interview_reply_graph.invoke`；业务逻辑保留于 `process_legacy`；`test_interview_agent_step1/3/4_step5` 共 16 项全绿。
- 2026-06-09：小步 6B——完整 §6.5 拓扑；`routing.py`；删除 `process_legacy` 与 `run_legacy_reply.py`；Handler 仅薄封装 `invoke`（Evidence 段后续由 05 替换 stub）。
- 2026-06-12：**文档与 commit 对齐** — 状态改为已完成；§14 反映 05 Evidence 已接入。

## 14. 收尾状态与未做项

### 14.1 小步 1–5：已完成

| 能力 | 状态 |
|---|---|
| 激活已确认计划 + 首问（opening 口语化 / 降级 plan 原文） | ✅ |
| Decide / Act 分离 + 允许动作校验 | ✅ |
| 单主题 / 整场硬边界（`boundaries.py`） | ✅ |
| `topic_summaries` + 每主题消息线程 | ✅ |
| `POST .../activate` / `reply/stream` / `finish` / `GET` 恢复 | ✅ |
| SSE（session_state / delta / progress / error / done） | ✅ |
| 前端 Live 页（进度、倒计时、收尾区、主动结束） | ✅ |
| 05 上下文接口（`get_interview_memory_context`） | ✅ 由 05 填充 |
| 后端测试（降级路径 + 边界） | ✅ |
| Reply 编排 | ✅ LangGraph 6B + 05 Evidence 节点 |

### 14.2 小步 6A / 6B：LangGraph 迁移

| 能力 | 6A | 6B |
|---|---|---|
| `interview_reply_graph` + `InterviewReplyState` | ✅ | — |
| `run_legacy_reply` 单节点透传 | ✅ | — |
| Handler `invoke` 薄封装 + pytest 全绿 | ✅ | ✅ |
| 多节点拆分（§6.5.4） | — | ✅ |
| `routing.py` + 条件边 | — | ✅ |
| `pass_through_evidence` stub | — | ✅（已由 05 替换） |
| 删除 `process_legacy` | — | ✅ |
| Checkpointer（可选） | — | ⬜ |

### 14.3 本专题明确不做 / 后续专题

| 项 | 说明 |
|---|---|
| 结构化工作记忆与 Evidence 业务 | 专题 **05**（本专题仅保留 Reply 图拓扑） |
| 正式能力评分与报告 | 专题 **06** |
| 真 LLM token 级流式 | 非 04 范围；当前为分块 SSE + 前端打字机 |
| §9.3 对话质量 LLM 路径抽检 | 需真实模型人工评测，非 CI 硬门禁 |

### 14.4 可选 polish（非阻塞 04 关闭）

- `evaluating` → `completed` 与 06 评估报告占位 UI 打通。
- 预览页进入 Live 前的独立「开始前提示」卡片（当前文案在 Live 页 header）。
- 真实 LLM 路径集成测试 / 抽样人工评测（CI 默认 `FailingLLMClient`）。
