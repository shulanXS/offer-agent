# RAG 配置说明

出题阶段 Planning RAG：从 Milvus Lite 检索岗位知识库，辅助生成更贴合岗位的面试题。

配置项写在 `backend/.env`，知识文档放在 `backend/knowledge/roles/`。

## 启用步骤

1. 填写下方 RAG 相关配置。
2. 将岗位知识 markdown 放到 `knowledge/roles/`（文档格式见 [knowledge/README.md](./knowledge/README.md)）。
3. 构建索引：

```bash
cd backend
python3 scripts/index_role_knowledge.py
```

4. 设置 `RAG_ENABLED=true` 并重启后端。

首次启动也可通过 `start.sh` 在 Milvus 库不存在时自动建索引（`RAG_ENABLED=true` 时）。

## 配置项

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `RAG_ENABLED` | 是否开启 RAG | `false` |
| `RAG_COLLECTION_NAME` | Milvus collection 名称 | `role_knowledge` |
| `RAG_TOP_K` | 每次检索返回的知识块数量 | `4` |
| `RAG_EMBEDDING_PROVIDER` | 向量生成方案：`local` / `openai` | `local` |
| `RAG_EMBEDDING_MODEL` | Embedding 模型名 | `hash-embedding-v1` |
| `RAG_EMBEDDING_DIMENSION` | 向量维度，须与模型一致 | `256` |
| `RAG_KNOWLEDGE_DIR` | 知识库根目录 | `./knowledge` |
| `MILVUS_LITE_DB_PATH` | Milvus Lite 数据库路径 | `./data/milvus_lite.db` |

## 向量生成方案

通过 `RAG_EMBEDDING_PROVIDER` **手动切换**，不会根据环境或 Key 是否配置自动切换。

切换 provider 或修改维度后，须**重新建索引**并**重启后端**。

### 方案 A — 本地哈希向量（默认）

适合离线开发调试。纯本地 SHA256 哈希，无需联网、无需 API Key。

```env
RAG_EMBEDDING_PROVIDER=local
RAG_EMBEDDING_MODEL=hash-embedding-v1
RAG_EMBEDDING_DIMENSION=256
```

- `RAG_EMBEDDING_MODEL` 在 `local` 模式下仅为占位名，代码中未使用。
- 基于词面匹配，非语义向量，检索质量低于真实 Embedding 模型。

### 方案 B — OpenAI 向量模型

适合正式上线，语义匹配更精准。

```env
RAG_EMBEDDING_PROVIDER=openai
RAG_EMBEDDING_MODEL=text-embedding-3-small
RAG_EMBEDDING_DIMENSION=1536
OPENAI_API_KEY=<你的密钥>
OPENAI_BASE_URL=https://api.openai.com/v1
```

- 须配置 `OPENAI_API_KEY`；兼容网关时填写 `OPENAI_BASE_URL`。
- 未配置 Key 时建索引或检索会直接报错，**不会**回退到 `local`。
- `text-embedding-3-small` 默认输出 **1536** 维；若换 `text-embedding-3-large`，维度改为 **3072**。
- `RAG_EMBEDDING_DIMENSION` 须与 API 实际返回长度一致，供 Milvus 建表与检索使用。

### 本地哈希 vs OpenAI 向量

| | 本地哈希 | OpenAI |
|--|---------|--------|
| 语义理解 | 否，词面匹配 | 是 |
| 联网 / Key | 不需要 | 需要 |
| 默认维度 | 256 | 1536 |
| 适用场景 | 离线调试 | 生产环境 |

## 与 LLM 的关系

RAG 向量与对话 LLM **相互独立**，但 OpenAI 方案会**共用**同一组环境变量。

- `LLM_PROVIDER` 决定出题/追问/评价用哪家**对话模型**；`RAG_EMBEDDING_PROVIDER` 决定知识库用哪种**向量模型**，两者互不自动切换。
- Anthropic **没有**官方 Embedding API——`LLM_PROVIDER=anthropic` 时，Anthropic Key 只用于对话，**不能**替代 RAG 向量。若 RAG 要用 OpenAI 向量（`RAG_EMBEDDING_PROVIDER=openai`），须额外配置 `OPENAI_API_KEY`（兼容网关时还有 `OPENAI_BASE_URL`）；仅有 Anthropic Key 时，RAG 建议用 `local`，或确认网关是否提供 OpenAI 兼容 Embedding 接口。
- 若大模型已是 OpenAI（`LLM_PROVIDER=openai`），`.env` 里通常已配好 `OPENAI_API_KEY` / `OPENAI_BASE_URL`——RAG 切到 `openai` 时**直接复用即可**，**不必再配一遍**；向量化与对话只是调用同一 Key 的不同 API。
- 常见组合：`LLM_PROVIDER=anthropic` + `RAG_EMBEDDING_PROVIDER=local`（对话走 Anthropic，向量本地）；或 `LLM_PROVIDER=openai` + `RAG_EMBEDDING_PROVIDER=openai`（Key 共用）。

LLM 配置详见 [LLM_README.md](./LLM_README.md)。
