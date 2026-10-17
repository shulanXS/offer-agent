# Offer Agent

前后端分离的 **AI 模拟面试官**：上传简历、配置校招/社招与可选 JD、生成并确认面试计划、动态追问、证据驱动评估与练习闭环。

## 结构

- `backend`：FastAPI + SQLite + JWT + LangGraph + Resume Parser + LLM Factory + alembic 迁移 + Stripe 支付
- `frontend`：React + Vite 单页应用，i18n 双语，SSE 真流展示面试官回复

## 后端分层

- `app/api`：HTTP 接口层
- `app/services`：业务编排（Planning / Interview / Evaluation 会话、订阅与配额、支付、入账事务、流式输出等）
- `app/agent`：三个 Agent 模块，由 services 直接调用，不走 HTTP
  - `interview_planning/`：生成与校验 `plan_json`
  - `interview/`：LangGraph 动态面试（Observe → Evidence → Decide → Act）
  - `interview_evaluation/`：评估叙事增强（评分主路径为规则 + 证据投影）
- `app/llm`：模型工厂与 Provider 适配
- `app/db`：SQLite 持久化（9 个 repository + `Store` 薄 facade + `transaction()` 上下文）
- `app/core`：配置、安全、流式工具、状态机、限流、领域事件名常量

## 能力

- JWT 登录与面试额度
- 简历上传与结构化解析（`pdf` / `txt` / `md` / `docx`）
- 面试配置：目标岗位、技术语言、难度、校招/社招、可选 JD 原文、重点练习方向
- Planning + HITL：计划预览、策略化重新生成（最多 2 次）、确认锁定
- 动态面试：按 `plan_json` 主题追问/切题，时长由 `configuration.duration_minutes`（15/30/45/60）决定，轮数与时间边界由代码强制
- 工作记忆与 Evidence Extraction，驱动缺口追问与可解释评分
- 评估报告：三态评分、证据引用、逐题复盘、JD 要点验证、练习建议
- 跨场次学习（部分）：评估页「与上一场对比」等
- SSE 流式输出（通过 LangGraph `astream_events(version="v2")` 订阅 `on_chat_model_stream` 拿真 LLM delta）与会话持久化
- 中英文 UI 切换（侧栏高对比度 Pill），i18n 词条覆盖 8 个 namespace × 2 语言
- 面试语言独立配置：在创建面试时选择 `interview_language = en | zh`，与 UI 语言解耦；评估报告、计划生成、面试追问均按 `interview_language` 输出
- 后端双语 options：`GET /api/interview-options` 按 `Accept-Language: en|zh` 返回对应 `label`
- SSE 流式重连与心跳：`consumeEventStream` 用 `AbortController`，15s 心跳 + `X-Request-Id` 重放；`requestJson` / `requestFormData` 默认 `keepalive: true`
- 离开页面冻结计时：`POST /api/interviews/{id}/pause` + `/{id}/resume`，`useInterviewPauseResume` hook 监听 `visibilitychange`
- 计划生成失败可重试：`PlanGenerationRetryableError` 全局 handler，前端可展示「换个模型重试」按钮（响应字段 `retryable_error.retryable`）
- 真实支付通道（Stripe，默认 `PAYMENT_PROVIDER=stripe`）：`payment_orders` 表 + `StripeProvider` + 订单/回调/落地页全链路；Provider 未配置 → 503，绝不退化为 mock
- 订阅与配额：`membership_status`（active_subscription / expired_subscription / paid / free）由 `apply_payment_to_user` + `sync_subscription_status` 统一维护；订阅有效时 `effective_quota_remaining` 返回 `None`（语义 = 无限）
- 算法回合：`include_algorithm=true` 时 live page 右侧 `app-algo-panel` 打开；LLM judge 强 JSON-only + 错误码白名单 + 限流；评分仅在 React state 展示，不写 messages
- 面试配置扩展：`target_role` 9 枚举（含 `__custom__`）+ `duration_minutes ∈ {15, 30, 45, 60}` + `include_algorithm` 开关
- 401 → 自动跳登录：`unauthorizedHandler` 统一处理 + 登录后跳回 `offer-agent-return-path`
- `SessionState` Enum + `assert_transition` 集中状态机
- `transaction()` 上下文 + `with_retry()` 串行化写入与指数退避重试
- `(session_id, request_id)` 唯一约束 + `find_message_pair_by_request_id` 按 seq 配对，幂等回复
- 进程内 `EventBus` 推 `evaluation_done`；评估分布式锁
- `store` 拆 9 个 repository；`Store` 退化为薄 facade
- `alembic` baseline（`v2_3_baseline` 一次性建表 + `v2_1_initial` 依赖）
- App.tsx 拆 `useAuthDialog` / `useResumes` / `useReturnUrl`；InterviewLivePage 拆 5 个子组件 + `useInterviewLiveState`
- 主题 class 统一为 `app-*` 前缀
- `backend/Dockerfile` 单 worker 单实例

  - `algo_title` / 算法回合相关文案已迁移至 `interview.json` 与 `common.json`。
- 等等，按 `i18next` 实际 namespace 加载约定同步。

详见 [`reference/`](reference/) 各专题笔记。

## 启动

默认前端 `http://localhost:5173`，后端 `http://localhost:8000`。

### Backend

**首次准备：**

```bash
cd backend
cp .env.example .env
# 编辑 .env，至少配置 LLM_PROVIDER 与对应 API Key（见 backend/LLM_README.md）

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**日常启动：**

```bash
cd backend
./start.sh
```

`start.sh` 会检查虚拟环境与 `.env`，默认 `--reload` 监听 `127.0.0.1:8000`。可通过环境变量覆盖，例如 `PORT=8001 RELOAD=false ./start.sh`。

### Frontend

**首次准备：**

```bash
cd frontend
npm install
```

拉取代码后若 `package.json` 或 `package-lock.json` 有变更，需重新执行 `npm install`。

**日常启动：**

```bash
cd frontend
npm run dev
```

本地开发无需配置 `frontend/.env`，Vite 会将 `/api` 代理到 `http://localhost:8000`。

## Vercel 前端部署

在 Vercel 中选择 `frontend` 为 Root Directory，Framework 选择 Vite，构建命令为 `npm run build`，输出目录为 `dist`，Node.js 使用 22 或更高版本。

前端 `vercel.json` 提供 SPA 页面回退；`/api` 不会回退到 HTML。上线完整功能前，在 Vercel 配置 `VITE_API_BASE_URL` 为后端 HTTPS 地址（不带末尾斜杠），然后重新部署。此变量会公开到浏览器，不应包含密钥。

FastAPI 后端需要独立运行，并配置持久化数据库、模型密钥和 JWT 密钥；当前 SQLite 文件不能作为 Vercel 无服务器实例中的持久存储。后端 `CORS_ORIGINS` 和 `FRONTEND_BASE_URL` 应配置为实际前端域名。云端环境变量优先于 `backend/.env`。

后端可使用 `backend/Dockerfile` 部署到 Railway，Root Directory 设置为 `/backend`，健康检查为 `/healthz`，挂载持久卷到 `/data` 并设置 `DATABASE_PATH=/data/offer_agent.db`。使用单实例、单 worker，避免本地 SQLite 跨实例分叉；日志路径可设置为 `/data/logs/offer_agent.log`。生产环境必须设置 `APP_ENV=production` 和随机生成且至少 32 字符的 `JWT_SECRET`，并注入模型 Provider 和对应 API Key。

## 模型配置

在 `backend/.env` 中配置 Provider 与 Key，字段说明见 [backend/LLM_README.md](./backend/LLM_README.md)。

- 支持 `openai`、`anthropic`（含 `claude` / `claude_code` 别名）、`volcengine`（含 `ark` 等别名）
- **已移除 mock 模式**：须配置有效 Key，真实 LLM 路径为产品主路径
- LLM 调用失败时，Planning / Interview / Evaluation 等模块走**规则降级**或**模板降级**，保证流程可继续

## 测试

```bash
cd backend
source .venv/bin/activate
pytest
```

CI 使用 `FailingLLMClient` 验证降级路径，不依赖真实模型 Key。

```bash
cd backend
.venv/bin/python -m pytest \
  tests/test_plan_retryable_error.py \
  tests/test_interview_planning.py \
  tests/test_planning_validator.py \
  tests/test_planning_pipeline_optimizations.py \
  tests/test_planning_prompts.py \
  tests/test_interview_configuration.py \
  tests/test_interview_memory_step1.py \
  tests/test_interview_memory_step2.py \
  tests/test_interview_memory_step3.py \
  tests/test_interview_memory_step4.py \
  tests/test_interview_evaluation_step1.py \
  tests/test_interview_evaluation_step2_unit.py
# 期望全绿

cd ../frontend && npm run build  # 期望 0 TS 错误
```

## 说明

- 默认数据库：`backend/data/offer_agent.db`（已在 `.gitignore`）
- 岗位知识 RAG 可选：仅 **Planning 阶段**在 `RAG_ENABLED=true` 时注入岗位知识；Interview / Evaluation 不使用
