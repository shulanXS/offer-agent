# 离线建索引：从知识库到 Milvus Lite

目录路径：实战项目 / AI面试智能体 / V1 版本开发 / 核心难点 / RAG 检索增强 / 离线建索引：从知识库到 Milvus Lite

[原页面](https://acn2lw4rwc26.feishu.cn/wiki/Cc43woRkuiVwX6k0bWRcPU8Hnjh)

在 RAG 功能落地使用前，首先需要完成岗位知识库的离线索引构建，这是保障后续检索效果的基础环节。

这篇就带大家完整梳理这套索引的搭建逻辑，详细讲解从原始知识文件到向量库的全流程。

#### 索引创建步骤

整个索引创建过程分为五个步骤：

![页面图片](../assets/335-59aede906d36729c.png)

##### 第一步：读取知识库

项目的岗位知识统一存放在 backend/knowledge/roles/ 目录下，目前支持 3 个核心岗位：

- backend_engineer.md → 后端开发工程师

- frontend_engineer.md → 前端开发工程师

- product_manager.md → 产品经理

选择 Markdown 格式的原因：JD 写法、考察维度、常见面试题都会经常迭代，通常由产品或内容同学生维护。Markdown 对他们来说比数据库直观：改内容走 PR，git 自动留痕，不需要写迁移脚本。

##### 第二步：按章节拆分知识块

每个知识文件都固定包含 4 个二级标题（##）章节，建索引时会按章节拆分，一个章节 = 一个知识块（chunk）：

1. 岗位 JD → jd

2. 必备技能 → skills

3. 常见面试题 → questions

4. 重点考察维度 → rubric

3 个岗位 × 4 个章节，最终生成 12 个知识块（chunk）：

![页面图片](../assets/335-27bff8347b9009db.png)

##### 第三步：给每个知识块加标签

在存入向量库前，每个知识块都会添加岗位、文档类型前缀标签，格式示例：

````
岗位：后端开发工程师
文档类型：常见面试题
章节：常见面试题
<原始章节内容>
````

标签把角色和文档类型写进文本，检索更准确。不加标签时，「后端常见面试题」和「产品经理常见面试题」在向量空间里可能很接近，检索容易串岗。

##### 第四步：生成向量

生成向量有两种方案可选，适配不同场景：

方案 1：RAG_EMBEDDING_PROVIDER = local （本地模式，默认）

- 无需 API Key，完全离线

- 采用哈希算法生成 256 维固定向量

- 适合本地调试，本项目数据量小，完全够用

方案 2：RAG_EMBEDDING_PROVIDER = openai（线上推荐）

- 需要配置 OpenAI API Key，生成语义向量

- 维度 1536，语义理解能力更强

- 适合生产环境、知识量增大的场景

![页面图片](../assets/335-115f18290b55785c.png)

这两项配置的详细说明，可查阅项目文档 backend/RAG_README.md，里面还包含更多环境参数与使用注意事项。

##### 第五步：写入 Milvus 向量库

生成的向量会存入 Milvus Lite，这是轻量级嵌入式数据库，类似 SQLite，只需要一个本地文件，无需单独启动服务），文件路径：./data/milvus_lite.db。

核心数据表（collection）：role_knowledge

> 图片尚未保存：[在原页面查看](https://acn2lw4rwc26.feishu.cn/wiki/Cc43woRkuiVwX6k0bWRcPU8Hnjh)（图片标识：WHIObfXfoorTI2xHiX1cDqPqnWg）

检索规则：先按岗位 ID 过滤，再做相似度排序，彻底避免跨岗位知识干扰。

#### 如何执行

离线建索引主要有执行两种方式，可根据场景灵活选择：

##### 1.
手动执行脚本

````
python3 scripts/index_role_knowledge.py
````

每次执行都会完整重建索引。适合修改知识库内容后使用。

##### 2.
启动脚本自动触发

````
# 第一步：在 .env 里开启配置
RAG_ENABLED=true
# 第二步：执行启动脚本
./start.sh
````

该方式会在向量库文件不存在时自动建索引，后续重复启动不会重复执行。 若需要每次启动都强制重建索引，额外开启配置 AUTO_INDEX_RAG=true 即可。

需重建索引的场景

以下情况必须重新跑建索引脚本：

- 修改了 knowledge/roles/ 下的 Markdown

- 切换了 RAG_EMBEDDING_PROVIDER（local ↔ openai）

- 修改了 RAG_EMBEDDING_DIMENSION

执行脚本后，会发现 backend/data 目录下多了一个 milvus_lite.db 的目录：

> 图片尚未保存：[在原页面查看](https://acn2lw4rwc26.feishu.cn/wiki/Cc43woRkuiVwX6k0bWRcPU8Hnjh)（图片标识：E05zbSgkGoDBbjxt22jcAbFSnhU）

现在不需要关心里面的具体内容，等在线检索时再测试 RAG 是否真的生效。