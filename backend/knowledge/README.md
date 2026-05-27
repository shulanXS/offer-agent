# 岗位知识库

该目录用于存放出题阶段 Planning RAG 所需的岗位知识文档。

当前内置岗位：

- `backend_engineer.md`：后端开发工程师
- `frontend_engineer.md`：前端开发工程师
- `product_manager.md`：产品经理

## 索引方式

1. 安装依赖：

```bash
pip install -r requirements.txt
```

2. 构建 Milvus Lite 索引：

```bash
python3 scripts/index_role_knowledge.py
```

3. 打开 `.env` 中的 `RAG_ENABLED=true`

## 文档约定

- 使用 `##` 二级标题拆分可检索的知识块。
- 当前索引器支持识别以下章节：
  - `岗位JD`
  - `必备技能`
  - `常见面试题`
  - `重点考察维度`
