# Offer Agent

一个前后端分离的脱敏教学版 CV 面试工程，支持上传简历、结构化解析、流式面试和可配置模型调用。

## 结构

- `backend`: FastAPI + SQLite + JWT + LangGraph 工作流 + Resume Parser + LLM Factory
- `frontend`: React + Vite 单页应用，支持 SSE 流式交互

## 后端分层

- `app/api`: HTTP 接口层
- `app/services`: 业务服务层，负责额度、会话恢复、流式编排
- `app/llm`: 模型工厂和 Provider 适配层
- `app/db`: SQLite 持久化层
- `app/agent`: 脱敏后的 CV 面试链路工作流，业务层通过方法调用，不走 HTTP
- `app/core`: 配置、安全、流式工具

## 能力

- 最简 JWT 登录体系
- 最简单的面试额度计数
- 可配置模型工厂，支持 `mock`、`openai`、`anthropic/claude`、`volcengine/ark`
- 简历上传与解析，形成 `cv_extract -> interview` 链路
- 脱敏后的 CV 面试链路：出题、追问、总结
- SSE 流式输出
- 会话持久化，刷新后恢复聊天记录
- 教学版类 ChatGPT 对话页面

## 启动

### Backend

```bash
cd backend
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

默认前端地址是 `http://localhost:5173`，后端地址是 `http://localhost:8000`。

## 模型配置

后端通过 `.env` 控制默认 Provider：

- `LLM_PROVIDER`: `mock` / `openai` / `anthropic` / `claude_code` / `volcengine`
- `LLM_MODEL`: 默认模型名
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `ANTHROPIC_API_KEY`
- `VOLCENGINE_API_KEY`
- `VOLCENGINE_BASE_URL`

未配置对应 Key 时，系统会自动回退到教学版规则逻辑。

## 说明

- 当前 `agent` 模块是教学版实现，保留工作流结构和接口形态，不暴露原线上最有价值的 Prompt、评分细则和模型路由策略。
- 默认数据存储在 `backend/data/offer_agent.db`，已加入 `.gitignore`。
- 上传解析支持 `pdf`、`txt`、`md`、`docx`。
# offer-agent
