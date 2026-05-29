# 大模型配置说明

全局模型开关，影响：简历解析、面试出题、追问、评价总结。

配置项写在 `backend/.env`，本节说明各字段含义与示例。

## 通用字段

| 变量 | 说明 |
|------|------|
| `LLM_PROVIDER` | 模型提供商，见下表 |
| `LLM_MODEL` | 模型名，须与网关/厂商文档一致 |
| `LLM_TIMEOUT_SECONDS` | 单次请求最长等待时间（秒），默认 300 |

### 支持的 LLM_PROVIDER

| 值 | 说明 |
|----|------|
| `mock` | 本地规则，不调用真实模型（适合离线调试） |
| `openai` | OpenAI 或 OpenAI 兼容网关 |
| `anthropic` | Claude / Anthropic 或兼容网关（`claude`、`claude_code` 同此路径） |
| `volcengine` | 火山方舟 / 豆包（`ark`、`volc`、`huoshan` 同此路径） |

## OpenAI 或 OpenAI 兼容网关

```env
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=<你的密钥>
OPENAI_BASE_URL=https://api.openai.com/v1
```

若云厂商提供 OpenAI 兼容接口，保持 `LLM_PROVIDER=openai`，修改 `OPENAI_BASE_URL` 与 `LLM_MODEL` 即可。

| 变量 | 说明 |
|------|------|
| `OPENAI_API_KEY` | API 密钥 |
| `OPENAI_BASE_URL` | 可选；代理、云网关或私有化部署时填写 |

## Claude / Anthropic 或兼容网关

```env
LLM_PROVIDER=anthropic
LLM_MODEL=MiniMax-M2.5
ANTHROPIC_API_KEY=<你的密钥>
ANTHROPIC_BASE_URL=https://aigw-gzgy2.cucloud.cn:8443
```

填写自定义 `ANTHROPIC_BASE_URL` 时，会用同一 `ANTHROPIC_API_KEY` 发送 `Authorization: Bearer` 头。

| 变量 | 说明 |
|------|------|
| `ANTHROPIC_API_KEY` | API 密钥 |
| `ANTHROPIC_BASE_URL` | 可选；兼容网关地址 |

## 火山方舟 / 豆包

```env
LLM_PROVIDER=volcengine
LLM_MODEL=doubao-seed-1-6-flash-250715
VOLCENGINE_API_KEY=<你的密钥>
VOLCENGINE_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
```

| 变量 | 说明 |
|------|------|
| `VOLCENGINE_API_KEY` | API 密钥 |
| `VOLCENGINE_BASE_URL` | 方舟 API 地址，默认见上 |

## 注意事项

- 未配置对应 Key 时，调用真实模型会直接报错（`mock` 除外）。
- 修改 `.env` 后须重启后端进程。
- LLM 配置与 RAG 向量配置相互独立，详见 [RAG_README.md](./RAG_README.md)。
