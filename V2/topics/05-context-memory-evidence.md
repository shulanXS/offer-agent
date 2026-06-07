# 上下文、记忆与证据

## 1. 文档状态

- 状态：**已完成**（小步 1–4）
- 对应路线图：阶段 7
- 核心能力：工作记忆、Evidence Extraction、主题摘要升级、Decide 消费 gaps、**Act 同主题追问自然过渡**
- 前置专题：[04 动态面试 Agent](./04-dynamic-interview-agent.md)（LangGraph Reply 图；Evidence 段已接入）
- 后续专题：[06 评估与练习闭环](./06-evaluation-and-practice.md)（消费证据）；跨场次长期记忆见 [07 跨场次学习档案](./07-cross-session-learning.md)（**部分已交付**，本专题不实现）

**04 接入点（05 已完成替换）：**

| 位置 | 现状 |
|---|---|
| `nodes/extract_evidence.py` → `merge_working_memory.py` | 每轮 Evidence 提取与 merge |
| `services/interview/context.py` | `get_interview_memory_context()` 填充 gaps / risks / contradictions |
| `services/interview/topic_summary.py` | 证据化主题摘要 |
| `runtime_state.working_memory` | 持久化工作记忆 |
| `agent/interview/decide.py` + `act.py` | 消费 `memory_context`；§7.4 同主题承接 |

## 2. 改造目标

让 Interview Agent 能区分两类本场上下文：

- **本场记忆**：候选人已经说过什么、还缺少什么、哪些声明已验证。
- **评估证据**：回答中能支持追问与后续评分的结构化 claims / evidence / risks。

本专题**不包含岗位知识 RAG 改造**（V2 暂不实施）。

完成后：

- Decide 不再只依赖「最新一条回答 + plan 字段」，而是读结构化 **gaps / 证据强度 / 已覆盖 signals**。
- Act 在同主题连续追问时**先承接 `latest_answer`，再追下一缺口**，避免「清单式跳题、话术断档」（见 §7.4）。
- Evaluation Agent（06）能消费按主题整理的 `evidence_by_topic`、`risks`、`unverified_items`。
- **`interview_knowledge=[]` 时，03 / 04 / 06 仍须完整可跑。**

## 3. 本专题范围

### 负责

- 当前主题短期记忆（在 04 基础上升级摘要与压缩策略）
- 本场结构化工作记忆（claims、evidence、risks、missing_information、contradictions）
- LangGraph 节点：`extract_evidence`、`merge_working_memory`（替换 04 stub）
- 主题摘要证据化升级（对外字段名保持 `topic_summaries`）
- `get_interview_memory_context()` 填充与 Decide / **Act** Prompt 扩展（§7.4）
- 潜在矛盾检测与验证性追问（待验证，不自动定罪）
- 向 06 导出 `evidence_by_topic`、`risks`、`unverified_items`

### 不负责

- Interview Agent 动作边界与时间/轮数硬规则（04 `boundaries.py` + 图条件边）
- Reply 图除 Evidence 段外的节点编排（04 已完成）
- 最终评分、报告页面与练习闭环 UI（06）
- JD 文件上传和解析（02）
- 跨场次长期记忆（[07 跨场次学习档案](./07-cross-session-learning.md)）

## 4. 依赖契约

### 4.1 消费

- **04**：`messages`（含 `meta.topic_id`）、`topic_summaries`（规则版）、动作轨迹、`runtime_state`、已锁定 `plan_json`。
- **02**：`configuration.jd_text` 原文仅作 Evidence / Decide 的**私有上下文**，不写入任何公共库。

### 4.2 输出

**向 04（`get_interview_memory_context`）— 本专题填充：**

```json
{
  "relevant_memory": {},
  "missing_information": [],
  "risks": [],
  "contradictions": [],
  "interview_knowledge": []
}
```

- 本专题实现**前四字段**；`interview_knowledge` **V2 恒为空数组**；04/05 不得因该字段为空而失败。
- `relevant_memory` 建议形状：`{ "current_topic_id": "...", "covered_signals": [], "recent_evidence": [] }`（具体键名在实现时于本文件实施记录钉死，须可映射到 plan）。

**向 06（会话结束或 evaluating 时读取）：**

```json
{
  "evidence_by_topic": {},
  "risks": [],
  "unverified_items": [],
  "evaluation_anchors": []
}
```

- 本专题提供前三项；`evaluation_anchors` **V2 恒为空**，06 使用本地锚点降级。
- `evidence_by_topic` 由 `runtime_state.working_memory` **确定性投影**（见 §5.4），不在 06 侧重新提取。

### 4.3 与 04 的边界（不重复开发）

| 能力 | 04（已完成） | 05（本专题） |
|---|---|---|
| Reply LangGraph 拓扑（ingest → observe → boundaries → … → decide → act/finalize） | ✅ | 已接入 extract → merge 段 |
| 每主题消息线程 + `meta.topic_id` | ✅ | 不重复 |
| 切题 `topic_summaries`（规则 1–3 句） | ✅ | 升级为证据化摘要 |
| 结构化 claims / evidence | ❌ | ✅ |
| Decide 读 `expected_signals` | ✅ | 叠加 gaps / 证据强度 |
| 避免重复追问已验证内容 | ❌（仅 `last_probed_information`） | ✅ 小步 3 |

**原则**：05 在 04 已落库数据上**增量写入** `runtime_state.working_memory`；不重写状态机、边界与 Act/Decide 分离架构；**图节点内禁止 Store / HTTP / SSE**（持久化仍在 `InterviewAgentService` invoke 后写 DB）。

### 4.4 旧能力处理边界

- **直接保留**：LLM Factory、结构化 JSON 校验、日志工具。
- **允许抽取**：Evidence 校验、工作记忆 merge、plan signal 映射（建议 `services/interview/memory/` 或 `agent/interview/evidence/`）。
- **替换重构**：04 规则版 `topic_summary.build_topic_summary` 的**内部实现**（对外字段名不变）。
- **禁止混用**：旧 V1 `question_threads` 存工作记忆；不把简历/JD/回答写入公共知识库。

### 4.5 与 plan_json 对齐（硬要求）

全链路主轴是专题 03 锁定的 `plan_json`。**05 不得引入第二套「考察维度」或「期望信号」词汇**；niumian 等外部经验只能用于 Prompt 写法，输出必须挂回 plan 字段。

**三层概念（禁止混用）：**

| 层级 | 来源 | 05 中的角色 |
|---|---|---|
| 考什么方向 | plan 主题 `dimension` / `name` / `objective` | 只读；写入 `topic_id` 索引，不重复存 dimension |
| 要听到什么 | plan 主题 `expected_signals` / `focus_points` | **缺口与覆盖的主键** |
| 怎么追 | 04 合法 `probe_*` action | 可选 `probe_hint`；由 Decide 最终选择 |

**Evidence / 工作记忆字段约束：**

- 所有 `evidence`、`missing_information`、`claims` 必须带 `topic_id`，且对应当前或历史 plan 主题。
- `missing_information[].signal` 必须是该主题 `expected_signals` 或 `focus_points` 中的**原文**（校验失败则丢弃该条，不写入工作记忆）。
- `evidence[].matched_signal` 同上；表示本条 quote 支撑了 plan 中哪条期望信号。
- `evidence[].polarity` 仅允许 `positive` / `negative` / `neutral`；**不得**用 `ownership`、`metric` 等别名替代 `matched_signal`。
- `claims[].probe_hint` 可选，且只能是 04 已有 `probe_*` action 之一。
- `covered_topics` / `uncovered_topics` 存 plan 主题 `id`；覆盖判定以 `expected_signals` 是否已有足够 evidence 为准。

**向 04 输出的 `missing_information` 每项形状：**

```json
{
  "topic_id": "topic-2",
  "signal": "个人贡献",
  "from_plan": true
}
```

Decide 的 `expected_information` 应**优先**取自上述结构，与 04 已有 `expected_signals` 读取**叠加**，不互相替代。

**向 06 输出的 `evidence_by_topic`：** 按 plan 主题 `id` 分桶；每桶须可还原：`expected_signals` 覆盖情况、quotes、risks；`dimension` / `name` 由 06 读 plan（推荐），05 不重复存一份 plan 快照除非 06 文档改为读快照。

**一致性验收（每轮或 CI 抽检）：**

1. 任意 evidence 是否可指向 `plan_json.topics[].id` 与至少一条 `expected_signals` / `focus_points`？
2. `missing_information` 是否不存在 plan 外的自造 signal 名？
3. 切题后 `topic_summaries[topic_id]` 是否与同 `topic_id` 的 evidence 桶一致？
4. Decide 接入工作记忆后，`expected_information` 是否与当前主题未覆盖 signals 相关？

**停止条件（对齐类）：** 出现与 plan 平行的 dimension / signal 枚举且被 Decide 或 06 主路径依赖时，视为本专题未通过验收。

## 5. 核心概念

### 5.1 短期记忆

当前主题最近问答（`topic_messages`）+ 已完成主题的压缩摘要（`topic_summaries`）；Observe / Decide 不必每次携带全量 `all_messages`。

### 5.2 工作记忆（持久化）

存于 **`interview_sessions.workflow_state` → `runtime_state.working_memory`**（首期不拆表）：

```json
{
  "schema_version": 1,
  "claims": [],
  "evidence": [],
  "risks": [],
  "contradictions": [],
  "missing_information": [],
  "covered_topics": [],
  "uncovered_topics": []
}
```

- `topic_summaries` **仍保留在 `runtime_state` 顶层**（04 契约）；05 切题时同步更新其内容，但不把 summaries 嵌进 `working_memory` 以免双写歧义。
- 刷新恢复：与 04 相同，整包 `workflow_state` 从 DB 读取；Evidence 失败时**保留旧 `working_memory`**，不写入非法片段。

### 5.3 向 06 投影（`evidence_by_topic`）

会话进入 `evaluating` 时，由后端**确定性函数**从 `working_memory` 生成（非 LLM 临场编造）：

```python
# 伪代码 — 实现须单测
evidence_by_topic[topic_id] = {
    "evidence": [...],           # 该 topic_id 下 evidence 条目
    "covered_signals": [...],    # 有足够 strength 的 matched_signal 去重列表
    "missing_signals": [...],    # plan expected_signals 减去 covered
}
unverified_items = [claims where status == "unverified"]
risks = working_memory.risks + contradictions  # 按 06 文档约定合并或分列
```

## 6. LangGraph 接入（替换 04 stub）

### 6.1 拓扑变更

04 已完成段（不变）：

```text
START → ingest_answer → build_observe → enforce_boundaries
  ├─ finish      → finalize_forced_finish → END
  ├─ next_topic  → finalize_advance        → END
  └─ continue    → …                       → decide → …
```

**05 仅替换 `continue` 分支上的 stub：**

```text
continue → extract_evidence → merge_working_memory → decide → …
```

- `build_observe` **仍在 boundaries 之前**；Evidence 在边界判定通过后再跑，避免对已强制 finish 的轮次浪费 LLM。
- `merge_working_memory` 将 extractor 输出校验后 merge 进 `state.runtime_state.working_memory`，并刷新 `memory_context`（供同轮后续 `decide` 读取——若 decide 只读 `runtime_state`，则 `memory_context` 可选，但 `build_observe` 与 07 契约建议保持写入）。

### 6.2 节点职责

| 图节点 | 类型 | 职责 |
|---|---|---|
| `extract_evidence` | LLM + 校验 | 读当前主题 plan、latest_answer、已有 working_memory；输出 §7.2 Schema |
| `merge_working_memory` | 确定性 | plan signal 映射校验、去重 merge、更新 `covered_topics` / `uncovered_topics`；失败则 no-op |

### 6.3 状态字段扩展

在 `InterviewReplyState`（`agent/interview/state.py`）增量添加：

```python
extraction_result: dict[str, Any]   # extract 节点输出（可选，merge 后可清空）
working_memory: dict[str, Any]      # merge 后与 runtime_state 同步
```

小步 2 前 `working_memory` 可为空 dict；列表 merge 若需 LangGraph reducer，仅在确有多节点并发写同一列表时再引入 `Annotated[..., reducer]`。

### 6.4 推荐目录

```text
backend/app/services/interview/
├── context.py              # get_interview_memory_context 实现填充
├── topic_summary.py        # 证据化摘要（小步 1）
└── memory/
    ├── schema.py           # Pydantic / 手写校验
    ├── merge.py            # merge_working_memory 纯函数
    ├── project.py          # evidence_by_topic 投影（06 用）
    └── signal_map.py       # expected_signals / focus_points 原文映射

backend/app/agent/interview/
├── evidence/
│   ├── extract.py          # InterviewEvidenceExtractor（LLM）
│   └── prompts.py
├── nodes/
│   ├── extract_evidence.py
│   └── merge_working_memory.py   # 删除 evidence_stub.py
└── graph.py                # 更新边：stub → extract → merge
```

持久化：**不在节点内写 DB**；`InterviewAgentService` 在 `invoke` 返回后把含 `working_memory` 的 `runtime_state` 写入 `workflow_state`（与 04 一致）。

## 7. Evidence Extraction 设计

### 7.1 输入

- `trace_id`、`session_id`（经 state 传入，仅用于日志与 `get_interview_memory_context`）
- 当前主题 plan 条目（`current_topic`）
- `topic_messages`、最新 user 回答
- `runtime_state.working_memory`（已有 claims / evidence）
- `topic_summaries` 中当前及已完成主题摘要（可选，控制 Prompt 体积）

### 7.2 输出

```json
{
  "answer_quality": "weak|partial|strong",
  "claims": [
    {
      "topic_id": "topic-1",
      "content": "负责订单服务架构设计",
      "status": "unverified",
      "probe_hint": "probe_ownership"
    }
  ],
  "evidence": [
    {
      "topic_id": "topic-1",
      "matched_signal": "个人贡献",
      "polarity": "positive",
      "quote": "我负责订单服务拆分和迁移",
      "strength": 0.7,
      "rationale": "说明了个人负责范围"
    }
  ],
  "missing_information": [
    {
      "topic_id": "topic-1",
      "signal": "结果指标",
      "from_plan": true
    }
  ],
  "risks": [],
  "potential_contradictions": []
}
```

字段约束见 §4.6。Extractor Prompt 可借鉴 niumian「如何识别贡献/指标/取舍类缺口」的**表述经验**，但输出 signal 名必须来自当前主题 plan。

### 7.3 更新规则

- 证据必须引用当前回答短句，不编造候选人未说过的事实。
- `matched_signal` / `missing_information.signal` 无法映射到当前主题 plan 时，**丢弃该条**，不 merge。
- 相同声明和风险去重；新 evidence 可增强或削弱同一 `matched_signal` 的覆盖度。
- 潜在矛盾只记录，不自动判定撒谎；`potential_contradictions` 应引用 claim `content` 或 quote。
- 切换主题时：`finalize_advance` 仍写 `topic_summaries`；05 升级其内容为证据化摘要，并保留关键 `matched_signal` + `quote` 引用。
- 提取失败：**保留旧工作记忆**；`get_interview_memory_context` 返回降级空 gaps，Decide 回退 04 行为。

### 7.4 对话层自然过渡（Act 规则，小步 3 必做）

**04 已知问题**：Decide 按 plan `expected_signals` **清单**选下一缺口时，Act 可能锚定 **opening 或更早轮次**，而跳过对 **`latest_answer` 的承接**，造成「两问之间没联系、上一问没收尾」——例如先问「独立负责 vs 协作」，候选人答完后，下一句直接跳回首答问「指标提升多少」。

**分工**：

| 层 | 05 解决什么 |
|---|---|
| Decide + 工作记忆 | **问什么**：下一缺口来自 `missing_information`，已覆盖 signal 不再选 |
| Act（本节） | **怎么说**：换缺口时先回应上一答，再引出新问题 |

**Act Prompt 增量要求**（`agent/interview/prompts.py` → `ACT_PROMPT`）：

1. **`probe_*` / `increase_difficulty` / `decrease_difficulty`**：须 **先 1 句承接 `latest_answer`**（概括、确认或点名候选人刚说的要点），**再**提出与 `expected_information` / 本句 `action` 相关的一个新问题；整句 40–120 字。
2. **承接对象**：默认承接 **`latest_answer`**；仅当 `latest_answer` 明显偏题或无效时，才简短说明后回到当前缺口，**不得**无故跳回 opening 或首答。
3. **换缺口时**：若本句 `action` 或 `expected_information` 与上一轮不同（例如 ownership → metric），承接句须体现「上一问已听到」，再自然转到新 signal；禁止无过渡的「你刚才提到…」且锚点来自 **两轮以前** 的内容。
4. **`next_topic`**：沿用 04 规则（先简短承接，再引入下一主题 opening）。
5. **禁止虚构**：不得编造候选人未说过的「你刚才提到 X」；X 必须出现在 `latest_answer` 或 `conversation_history` 中候选人侧文本。

**Act 实现增量**（`agent/interview/act.py`）：

- Prompt 注入：`expected_information`（已有）、可选 `last_action`（来自 `runtime_state.last_action`，经 state 传入 act 节点）。
- `build_template_fallback_act_message`（`services/interview/actions.py`）同步遵守上述承接规则，避免 LLM 降级时话术断档。

**与 Decide 协同**：

- Decide 选定 `action` + `expected_information[0]`（来自 `missing_information[].signal` 映射）。
- Act 负责把 **决策缺口** 用 **对话线程** 说出来；Decide 不负责生成承接句。

**反例（验收必须避免）**：

```text
追问 1：哪些独立负责、哪些协作？
候选人：消息逻辑/表结构独立；网络层/推送协作…
追问 2：你刚才提到对消息收发做了优化，延迟提升多少？   ← 无承接、跳回首答
```

**正例**：

```text
追问 2：独立和协作的边界你说清楚了。想再补一下：改造后消息延迟和读写性能大概提升了多少？
```

## 8. 分步实施

### 小步 1：主题摘要与上下文压缩

**目标**：长对话 Prompt 可控；为 Evidence 打基础。

**实现：**

- 升级 `services/interview/topic_summary.py`（可 LLM 压缩，失败则现有规则降级）。
- `build_observe_context` / `get_interview_memory_context` 读 `topic_summaries` + 当前 `topic_messages`，限制注入 Decide 的历史条数或 token（配置项可选）。
- 初始化 `runtime_state.working_memory = { "schema_version": 1, ...空列表 }`（`build_initial_runtime_state` 或首次 merge 时 lazy init）。

**不实现：** 结构化 Evidence、图节点替换、Decide 行为变更。

**验证：**

- 现有 `test_interview_agent_step*` 16 项仍全绿。
- 新增：多主题切题后 `topic_summaries` 非空且可恢复；Observe 上下文体积有上限（单测或日志断言）。

**完成条件：** 长对话/多主题后上下文可控，刷新可恢复；04 无 Evidence 时行为与现网一致。

---

### 小步 2：Evidence Extraction + 图节点接入

**目标**：每轮回答后结构化提取并持久化；替换 04 stub。

**实现：**

- 新增 `memory/schema.py`、`memory/merge.py`、`evidence/extract.py`、`evidence/prompts.py`。
- 新增 `nodes/extract_evidence.py`、`nodes/merge_working_memory.py`；**删除** `evidence_stub.py`。
- 更新 `graph.py`：`pass_through_evidence` → `extract_evidence` → `merge_working_memory` → `decide`。
- `get_interview_memory_context` 填充 `missing_information`、`risks`、`contradictions`、`relevant_memory`（来自 `working_memory`）。
- LLM 失败：extract 返回空增量，merge no-op。

**不实现：** Decide Prompt 变更、矛盾追问策略。

**验证：**

- 新增 `tests/test_interview_memory_step2.py`：Schema 校验、plan 外 signal 丢弃、quote 必须来自 `latest_answer`、merge 失败不 corrupt、图 invoke 后 `workflow_state.working_memory` 持久化。
- 现有 16 项回归全绿（Extractor 失败降级路径下行为等同 04）。

**完成条件：** 每轮稳定更新工作记忆；异常不污染旧状态；面试完整可跑。

---

### 小步 3：Decide 消费工作记忆 + Act 自然过渡

**目标**：工作记忆**实际改变**追问/切题倾向；同主题连续追问**话术不断档**（§7.4）。

**实现：**

**Decide：**

- 扩展 `agent/interview/decide.py` Prompt：注入 `memory_context.missing_information`、`covered_signals`、近期 evidence 摘要。
- `rule_fallback` 叠加：当前主题 gaps 为空且已有 strong evidence 时倾向 `next_topic`；高优先级 missing 映射到 `expected_information`。
- 与 04 `last_probed_information` / `should_block_repeat_probe` 协同：**已验证 signal 不再作为 missing 重复追问**。

**Act（§7.4，与小步 3 同批交付，不延后）：**

- 更新 `ACT_PROMPT`：`probe_*` 等须先承接 `latest_answer` 再问新缺口；换 action/signal 时禁止无过渡跳回 opening。
- `act.py` / `act_probe` 路径：可选传入 `last_action`；Prompt 带入 `expected_information[0]` 作为本句目标 signal。
- `build_template_fallback_act_message`：模板也采用「承接 + 追问」结构。

**不实现：** 06 报告。

**验证：**

- 新增 `tests/test_interview_memory_step3.py`：
  - **Decide**：mock `memory_context`，断言 action / `expected_information` 随 gaps 变化。
  - **Act（轻量）**：固定 `decision` + `latest_answer` + `topic_messages`，断言生成话术（或 template fallback）**包含**对 `latest_answer` 要点的引用/概括，且 **不包含**仅锚定 opening 的跳回模式（可用关键词/heuristic 或 snapshot 测 template 路径）。
- 场景用例（文档化，人工 + 可选 mock LLM）：
  - **ownership → metric**：候选人已答协作边界 → 下一句须承接该答再问指标（§7.4 正/反例）。
  - 覆盖充分 → 切题；缺口明确 → 追问对应 signal。

**完成条件：** 工作记忆改变 Decide 行为（可测）；§4.6 验收项 4 通过；§7.4 反例在人工抽检中不再出现；Act template 降级路径有单测覆盖。

---

### 小步 4：潜在矛盾检测

**目标**：矛盾仅作待验证风险，不自动定罪。

**实现：**

- Extractor 或独立轻量步骤：新 claims 与历史 evidence / claims 比较 → `contradictions` / `risks`。
- Decide：至多 **1 次**验证性追问（`probe_*`）；不自动 `finish` 或降分。
- 06 投影包含 `unverified_items` 与矛盾条目。

**验证：**

- 矛盾写入可恢复；不会在没有追问机会时直接写入「撒谎」类结论。
- 04 边界（追问上限、轮数）仍优先于 Agent。

**完成条件：** 矛盾仅作待验证风险；§10 停止条件 4 不触发。

---

## 9. 测试与验收

### 9.1 自动化（CI）

| 类别 | 要求 |
|---|---|
| 回归 | 04 的 `test_interview_agent_step1/3/4_step5` 共 16 项始终全绿 |
| Schema | Evidence 输出通过校验；非法条目不 merge |
| Plan 对齐 | 每条 evidence / missing 可映射 plan `topic_id` + signal 原文（§4.5） |
| 容错 | Extract / merge 失败不 corrupt 已有 `working_memory` |
| 隔离 | `interview_knowledge=[]` 时全流程可跑 |
| Decide | 小步 3 起：memory 改变 action / `expected_information`（非仅写库） |
| Act 过渡 | 小步 3 起：同主题换缺口时先承接 `latest_answer`（§7.4；template 路径可 CI） |

### 9.2 人工（真实 LLM）

- 摘要/提取质量：quote 是否忠实原话、signal 是否来自 plan。
- 追问是否对准 gaps，充分覆盖后是否自然切题。
- **对话过渡（§7.4 必检）**：同一主题内连续两次 `probe_*` 时，第二问是否先回应上一答再追新缺口；是否出现「无承接、跳回 opening/首答」。
- **回归样例**：ownership 问完 → 候选人分独立/协作 → 下一问若追 metric，须类似 §7.4 正例，不得为 §7.4 反例。
- 候选人端**不展示**内部 evidence / risks（产品规则不变）。

### 9.3 可观测

- 普通日志不记录完整回答、简历、JD。
- 记录：`trace_id`、evidence/risks 数量、extract/merge 耗时、降级标记、plan 外丢弃条数。
- 限制每轮注入 Decide 的 evidence 条数（防 Prompt 膨胀）。

## 10. 停止条件

- 工作记忆等价于全文聊天记录堆叠。
- 证据含未出现的候选人事实。
- Decide 不读工作记忆（小步 3 完成后仍只读最新一句）。
- 小步 3 完成后，同主题换缺口时 Act 仍无承接、频繁跳回 opening（§7.4 反例在人工抽检中仍系统性出现）。
- 存在与 plan 平行的 signal / dimension 枚举，且被 Decide 或 06 主路径依赖（§4.5）。
- 替换 stub 后 04 边界测试失败或图内出现 Store/HTTP 调用。

## 11. 给 AI 的执行指令

```text
阅读 V2/ROADMAP.md、03-planning-and-human-in-the-loop.md、04-dynamic-interview-agent.md（§4.3、§6.5）和本文件。
04 已完成：勿改 boundaries / routing / finalize 语义；勿改 Planning/Evaluation 图。
一次只完成一个小步；完成后只更新本文件 §12 实施记录与 §13 进度表。
图节点内禁止 Store/HTTP/SSE；持久化留在 InterviewAgentService。
Evidence 必须挂回 plan_json 的 topic_id 与 expected_signals/focus_points 原文。
不要实现 06 评分 UI或 07 跨场档案。
测试必须用 backend/.venv/bin/python -m pytest；不要 pip install。
```

## 12. 实施记录

### 小步 1（2026-06-09）

- `services/interview/memory/schema.py`：`working_memory` Schema、`empty_working_memory()`、`ensure_working_memory()`、`attach_working_memory_if_missing()`。
- `services/interview/runtime_state.py`：`build_initial_runtime_state` 初始化 `working_memory`。
- `services/interview/topic_summary.py`：规则证据化摘要（plan 信号匹配 + 要点）；超长对话可选 LLM 压缩，失败降级规则版。
- `services/interview/context_limits.py`：`trim_topic_messages()`、`estimate_context_chars()`。
- `services/interview/context.py`：`get_interview_memory_context` 读 `working_memory` + `topic_summaries` 填充 `relevant_memory`；`build_observe_context` 输出 `context_topic_messages` 与 `context_char_estimate`。
- `core/config.py`：`interview_context_max_messages`、`interview_context_max_chars`、`interview_topic_summary_llm_min_chars`。
- `nodes/ingest.py`：legacy 会话 lazy init `working_memory`。
- `nodes/observe.py`、`nodes/decide_node.py`：Decide 使用裁剪后的 `context_topic_messages`（Act 仍用完整 `topic_messages`）。
- `nodes/finalize.py`：切题摘要传入 `topic_messages`。
- 测试：`tests/test_interview_memory_step1.py`（7 项）；04 回归 16 项全绿。

### 小步 2（2026-06-09）

- `services/interview/memory/signal_map.py`：plan `expected_signals` / `focus_points` 原文映射。
- `services/interview/memory/extraction_schema.py`：Evidence 提取结果校验（quote 必须来自 `latest_answer`、plan 外 signal 丢弃）。
- `services/interview/memory/merge.py`：增量 merge、`missing_information` / 主题覆盖确定性重算；LLM 失败 no-op 不 corrupt。
- `services/interview/memory/project.py`：`evidence_by_topic` 投影（供 06）。
- `agent/interview/evidence/extract.py` + `prompts.py`：`InterviewEvidenceExtractor`（LLM + 校验 + 空增量降级）。
- `nodes/extract_evidence.py`、`nodes/merge_working_memory.py`；删除 `evidence_stub.py`。
- `graph.py`：`continue → extract_evidence → merge_working_memory → decide`。
- `context.py`：`get_interview_memory_context` 填充当前主题 `missing_information` / `risks` / `contradictions` / `relevant_memory`。
- `state.py`：新增 `extraction_result`。
- 测试：`tests/test_interview_memory_step2.py`（8 项）；04 回归 + 小步 1 共 31 项全绿。

### 小步 3（2026-06-09）

- `memory/decide_support.py`：gaps 过滤、`topic_is_sufficiently_covered`、`memory_has_actionable_coverage`、`probe_action_for_signal`。
- `act_support.py`：回答短句截取与承接桥接。
- `decide.py` + `prompts.py`：Decide Prompt 注入 `covered_signals` / `missing_information` / evidence 摘要；传入 post-merge `memory_context`。
- `rule_fallback.py`：gaps 为空且已覆盖 → 切题；有 actionable coverage 时按缺口选 `probe_*` 与 `expected_information`；首轮无 evidence 时保留 04 长度降级。
- `act.py` + `prompts.py` + `actions.py`：§7.4 承接规则；template fallback「桥接 + 追问」；`last_action` / `target_signal` 注入。
- `nodes/decide_node.py`、`nodes/act_probe.py`：接入 `memory_context` / `last_action`。
- 测试：`tests/test_interview_memory_step3.py`（6 项）；累计 37 项全绿。

### 小步 4（2026-06-09）

- `memory/contradictions.py`：确定性矛盾检测（claims/evidence 极性冲突、对立表述）；`sanitize_contradiction_description` 禁止「撒谎」类定论。
- `merge.py`：merge 时合并 Extractor `potential_contradictions` + 检测结果。
- `runtime_state`：新增 `contradiction_verification_used`（全场最多 1 次验证性追问）。
- `decide_support.py` + `rule_fallback.py`：待核实矛盾优先触发 1 次 `probe_detail` 澄清；已使用后回退 gaps 逻辑。
- `decide.py` + `prompts.py`：Decide 读 `pending_contradictions`；`decide_node` 标记 verification used。
- `project.py`：06 投影输出 `contradictions`、`unverified_items`，risks 合并矛盾描述。
- `actions.py`：验证性追问 template「想确认一下…」中性话术。
- 测试：`tests/test_interview_memory_step4.py`（7 项）；累计 44 项全绿。

## 13. 收尾状态与未做项

### 13.1 小步进度

| 小步 | 内容 | 状态 |
|---|---|---|
| 1 | 主题摘要升级 + working_memory 初始化 + Observe 体积控制 | ✅ |
| 2 | Evidence Extraction + 图节点 + merge + context 填充 | ✅ |
| 3 | Decide 消费 gaps + Act 同主题追问自然过渡（§7.4） | ✅ |
| 4 | 潜在矛盾检测与验证性追问 | ✅ |

**05 核心闭环已完结。** 跨场次长期记忆见 [07 跨场次学习档案](./07-cross-session-learning.md)（部分已交付）。

- 2026-06-12：**文档与 commit 对齐** — §1 状态改为已完成；接入点表与 §4.1 与代码一致。

### 13.2 04 已就绪、05 直接复用

| 项 | 状态 |
|---|---|
| `pass_through_evidence` stub 占位 | ✅（已替换为 extract → merge） |
| `get_interview_memory_context()` 空实现 | ✅（小步 2 已填充） |
| `build_observe_context` + `observe_context` 入 state | ✅ |
| `runtime_state.topic_summaries` 切题写入 | ✅ |
| Reply 图 boundaries → continue 分支 | ✅ |

### 13.3 本专题明确不做

| 项 | 说明 |
|---|---|
| Reply 硬边界 / 轮数 / 时间 | 04 |
| 评估报告与练习 UI | 06 |
| 跨场次学习档案与趋势 | 07 |
| 真 token 级流式 | 04 范围外 |
