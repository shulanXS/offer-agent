# 启动文档

## 前提

- Python 3.10+ / Node 20+
- `backend/.env` 已配置（参考 `backend/.env.example`）
- DeepSeek 配置示例：
  ```
  LLM_PROVIDER=openai
  LLM_MODEL=deepseek-flash
  OPENAI_API_KEY=你的Key
  OPENAI_BASE_URL=https://api.deepseek.com
  ```

## 启动

```bash
# 终端 1：后端
cd backend
python3 -m venv .venv && source .venv/bin/activate  # 首次执行后省略
pip install -r requirements.txt                       # 首次执行后省略
./start.sh

# 终端 2：前端
cd frontend && npm install && npm run dev
```

访问：http://localhost:5173

## 关闭

```bash
# 后端
pkill -f "uvicorn app.main:app"

# 前端
pkill -f "vite"
```
