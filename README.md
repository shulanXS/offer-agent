# Offer Agent

前后端分离的 **AI 模拟面试官**：上传简历、配置校招/社招与可选 JD、生成并确认面试计划、45 分钟动态追问、证据驱动评估与练习闭环。

## 结构

- `backend`：FastAPI + SQLite + JWT + LangGraph + Resume Parser + LLM Factory
- `frontend`：React + Vite 单页应用，SSE 流式展示面试官回复

## 后端分层

- `app/api`：HTTP 接口层
- `app/services`：业务编排（Planning / Interview / Evaluation 会话、额度、流式输出等）
- `app/agent`：三个 Agent 模块，由 services 直接调用，不走 HTTP
  - `interview_planning/`：生成与校验 `plan_json`
  - `interview/`：LangGraph 动态面试（Observe → Evidence → Decide → Act）
  - `interview_evaluation/`：评估叙事增强（评分主路径为规则 + 证据投影）
- `app/llm`：模型工厂与 Provider 适配
- `app/db`：SQLite 持久化
- `app/core`：配置、安全、流式工具

## 能力

- JWT 登录与面试额度
- 简历上传与结构化解析（`pdf` / `txt` / `md` / `docx`）
- 面试配置：目标岗位、技术语言、难度、校招/社招、可选 JD 原文、重点练习方向
- Planning + HITL：计划预览、策略化重新生成（最多 2 次）、确认锁定
- 动态面试：按 `plan_json` 主题追问/切题，45 分钟与轮数边界由代码强制
- 工作记忆与 Evidence Extraction，驱动缺口追问与可解释评分
- 评估报告：三态评分、证据引用、逐题复盘、JD 要点验证、练习建议
- 跨场次学习（部分）：评估页「与上一场对比」等
- SSE 流式输出与会话持久化

## v1.1 新增能力

- **中英文 UI 切换**（侧栏 `EN | 中文`），i18n 词条覆盖全 7 个 page + 8 个 evaluation 子组件
- **面试语言独立配置**：在创建面试时选择 `interview_language = en | zh`，与 UI 语言解耦；评估报告、计划生成、面试追问均按 `interview_language` 输出
- **后端双语 options**：`GET /api/interview-options` 按 `Accept-Language: en|zh` 返回对应 `label`
- **SSE 流式重连与心跳**：`consumeEventStream` 用 `AbortController`，15s 心跳 + `X-Request-Id` 重放
- **离开页面冻结计时**：`POST /api/interviews/{id}/pause` + `/{id}/resume`，`useInterviewPauseResume` hook 监听 `visibilitychange`
- **计划生成失败可重试**：`PlanGenerationRetryableError` 全局 handler，前端可展示「换个模型重试」按钮（响应字段 `retryable_error.retryable`）
- **LLM 流式并发安全**：`LLMStreamPatcher` 用 `contextvars.ContextVar` 隔离每请求的 delta queue，无串扰

详见 [`改进方案.md`](改进方案.md) §13。

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

### v1.1 验收测试

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
# 期望 65 passed

cd ../frontend && npm run build  # 期望 0 TS 错误
```

## 说明

- 默认数据库：`backend/data/offer_agent.db`（已在 `.gitignore`）
- 岗位知识 RAG 可选：仅 **Planning 阶段**在 `RAG_ENABLED=true` 时注入岗位知识；Interview / Evaluation 不使用
