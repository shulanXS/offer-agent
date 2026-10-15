# 07 API 与数据层：从接口约定到并发风险

## 1. 核心接口按业务阶段理解

所有面试路由前缀为 `/api/interviews`。与其背接口数量，不如理解哪些操作需要前一个阶段产生的数据。

| 方法与相对路径 | 业务作用 | 主要前置条件 |
|---|---|---|
| POST 空路径 | 创建会话并生成计划 | 合法配置、本人简历 |
| GET /{id} | 获取规划或正式会话详情 | 会话属于当前用户 |
| POST /{id}/plan/generate | 获取或生成首版计划 | 规划服务允许的状态 |
| POST /{id}/plan/regenerate | 创建调整后的版本 | plan_ready、未超过版本额度 |
| POST /{id}/plan/confirm | 确认最新计划 | plan_ready |
| POST /{id}/activate | 激活正式面试 | plan_confirmed、额度可用 |
| POST /{id}/reply/stream | 提交回答并展示结果 | active、没有已知在途回复 |
| POST /{id}/finish | 用户主动结束 | active；已结束可返回现状 |
| POST /{id}/evaluate | 生成或返回报告 | evaluating，或 completed 且已有报告 |
| GET /{id}/evaluation | 读取已有报告 | 可评估会话与当前用户匹配 |
| GET /{id}/learning-context | 获取相关学习上下文 | 当前用户拥有该会话 |

具体字段以 schemas 和路由为准。这张表不是绕过状态校验的调用脚本。

## 2. 登录与资源归属是两道不同检查

HTTPBearer 提取令牌，JWT 解码校验签名和过期时间，再由 sub 查用户。缺失、无效令牌与不存在用户会得到认证错误。

认证通过只说明“你是谁”，不说明“这个 session_id 属于你”。服务调用 Store 时使用 user_id 与资源 ID 查询，简历引用同样要核对归属。UUID 复杂难猜只能降低猜测机会，不能代替授权。

密码采用 argon2 哈希（v1 阶段使用 PBKDF2-HMAC-SHA256，老用户登录成功后惰性 rehash 升级）。验证使用恒定时间比较。JWT 签名不加密载荷，令牌中不应放入需要保密的简历原文。生产配置还需要替换默认签名密钥，详见第 11 章。**v2.2 起**：注册和登录入口对 `username` 做 `strip().lower()` 归一，规避大小写差异导致的"同账号进不去"问题；schema 加 `_no_blank` field validator 拒绝纯空白 username/password。

## 3. 数据表怎样对应业务

users 保存身份和额度；resumes 保存文件名与解析载荷；interview_sessions 保存会话状态、配置、运行态和评估；interview_plans 保存多版本计划及候选人摘要；messages 保存有序对话和元数据；learning_session_outcomes 保存单场学习快照；user_learning_profiles 保存聚合档案。

消息的 seq 用于排序，meta_json 提供 topic_id、action 和 trace_id 等信息。工作记忆不是独立的记忆数据库，而是运行态 JSON 的组成部分。

JSON 便于快速演进复杂模型输出，但数据库很难直接对内部字段建立强约束。若将来需要按证据统计、修订或审计，可考虑独立表与版本字段；不能仅为“规范”把所有 JSON 拆表，先明确查询与一致性需求。

## 4. 当前事务边界在哪里

Store 中多个方法各自建立连接并提交。因此确认计划的两个更新、激活时扣额度与写开场、回复时写用户消息与更新运行态，都不天然属于同一个业务事务。

例如激活在扣额度后生成开场，再次检查是否已经激活。顺序重复请求有返回已有会话的保护，但若两个请求同时通过前置检查，仍可能重复扣额度。应把“已有防重复逻辑”与“并发幂等性已证明”分开。

数据库定义了外键语法，但连接函数中没有显式启用 foreign_keys。不能仅看 CREATE TABLE 的 REFERENCES 就宣称运行时所有关联都由 SQLite 强制保护。计划版本索引也不是唯一约束，版本竞争需要另行处理。

## 5. 回复锁为什么只是第一步

reply_in_progress 在运行态中记录处理状态，可以拦截后到的常见重复请求。详情读取会根据最后消息或过期时间清理可能遗留的标记，默认过期阈值为 300 秒。

但“读标记为空 → 写 true”不是原子抢锁。两个并发请求可以都读到空。过期清理也可能与一个仍然工作的慢请求冲突。因此不应把这个布尔值描述成 Redis 锁或跨 worker 分布式锁。

演进方案：用数据库条件更新原子获得处理权，携带 state_version；为一次回答设置客户端请求 ID 与唯一约束；计算后按预期版本提交消息与新状态；重复请求返回同一处理结果。慢任务再增加任务状态和租约。模型调用期间不持有长事务。

## 6. 三种重复请求语义

重复确认目前返回 409，不是重复成功；重复激活有读取已有状态的保护；已完成的评估有报告则直接返回。不同接口可以有不同语义，但前端必须理解，不能把所有失败都当成“安全重试即可”。

对于模型处理较长的回复，客户端超时不能证明后端没有完成。先查询最新会话和最后消息，再决定是否重发，这是当前使用层面的稳妥步骤；彻底解决仍需请求级幂等协议。

## 7. 索引和演进怎样讲

会话按用户和更新时间查询，消息按会话和 seq 排序，计划按会话与版本查询，学习结果按档案维度查询，现有索引对应这些访问模式。

启动时 init_db 创建缺失表并补充部分字段，是轻量初始化方式，不等于完整迁移系统。正式演进需要版本化迁移、旧 JSON schema 兼容、备份及失败恢复。更换数据库或扩容前，应先明确这些需求。

## 8. v2.2：充值与算法题（mock 支付 + LLM judge）

**充值（`/api/billing/*`）**

- `GET /api/billing/packages` — 返回两个档位（`single` ¥20/5 次、`subscription` ¥200/30 天）+ 当前用户 tier/quota/subscription_expires_at
- `POST /api/billing/recharge` body `{package: 'single' | 'subscription'}` — 走 mock 支付：写 `payments` 审计表 + 事务内更新 `users.tier`/`quota_remaining`/`subscription_expires_at`
- `GET /api/billing/history` — 当前用户充值流水

**users 表新增列**：`tier`（free / paid / subscription）、`subscription_expires_at`（nullable）。**payments 表（新增）**：审计每一笔 mock 交易，PK 为 `id` 字符串，FK 到 `users.id`。

**订阅豁免额度**：`decrement_quota_in_conn` / `compensate_quota_in_conn` 在事务内先调 `is_subscription_active(user)`：订阅有效 → 写 0 delta 审计，不扣 quota；否则走原 quota 路径。`is_subscription_active` 比较 `subscription_expires_at` 与 `datetime.now(timezone.utc)`，显式 UTC 避免漂移。

**新用户免费额度**：`register` 时显式设 `quota_remaining = settings.new_user_free_quota`（默认 1），`tier = 'free'`。老用户 grandfather：`init_db` 时不强制改 quota_remaining，仅在缺失 `tier` 列时补默认值。

**算法题（`/api/algorithm/*`）**

- `GET /api/algorithm/problems` — 题库摘要列表（不返回 hidden_tests）
- `GET /api/algorithm/problems/{id}` — 单题详情
- `POST /api/algorithm/judge` body `{problem_id, code, language}` — 调用 LLM 模拟执行 + 评分；评分维度 correctness / efficiency / style / edge_cases（1-5）+ 整体 overall；解析失败时 `verdict=unparsed` 兜底而非 500

**算法分数不持久化到 messages.meta_json**，避免污染面试对话流；只在 live page 侧边栏展示当前回合结果。

## 9. v2.2：面试配置扩展

`POST /api/interviews` 入参在 v2.2 新增：

- `duration_minutes: Literal[15, 30, 45, 60] = 45` — 替代写死 45，激活时按此计算 `deadline_at`
- `include_algorithm: bool = False` — 标记本场是否含算法回合
- `custom_target_role: str | None` — 当 `target_role='__custom__'` 时必填
- `focus_topics` 上限从 6 提到 8（`MAX_FOCUS_TOPICS`）

`target_role` 枚举从 4 个扩展到 9 个（+ `data_ml` / `mobile` / `qa` / `sre` / `embedded` / `__custom__`）；`INTERVIEW_TYPES` 加 `intern`（实习）；`LANGUAGES` 在 schema 仍保留（兼容老数据），但前端 UI 已移除 `language` 字段让用户选择 LLM 输出的目标语种（v1.1 的 `interview_language` 字段独立保留，仍按 session 维度控制 LLM 输出语言）。

`GET /api/interview-options` 返回新增 `duration_minutes_options` / `include_algorithm_supported` / `focus_topics_recommended`，前端用这些字段驱动配置页。

## 核对与自测

源码：`backend/app/api/routes/interviews.py`、`backend/app/api/deps.py`、`backend/app/core/security.py`、`backend/app/db/store.py`。

练习：画出两个激活请求交错执行的时间线，找出重复额度扣减的窗口，再写出需要原子保护的条件。只画流程，不要求先实现修复。
