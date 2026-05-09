# 数据存储设计文档

## 存储选型

当前使用 **SQLite** 作为唯一的持久化存储，没有引入任何外部服务（Redis、PostgreSQL 等）。

选择 SQLite 的原因很直接：这是一个教学版单机应用，部署目标是开发者本地或单台服务器，不需要处理多实例并发写入，也不需要运维一套独立的数据库服务。SQLite 的数据库就是一个文件（`data/offer_agent.db`），零配置启动，迁移和备份都是复制文件。

数据库文件路径通过配置项 `database_path` 控制，默认在 `backend/data/offer_agent.db`，支持通过 `.env` 修改。

---

## 表结构

系统共有 4 张表，在应用启动时通过 `init_db()` 自动创建（`CREATE TABLE IF NOT EXISTS`），不依赖外部迁移工具。

### users

存储用户账号信息。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 自增主键 |
| username | TEXT UNIQUE | 用户名，唯一约束 |
| password_hash | TEXT | bcrypt 哈希，不存明文 |
| quota_remaining | INTEGER | 剩余面试次数，默认 5 |
| created_at / updated_at | TEXT | ISO 8601 UTC 时间戳 |

`quota_remaining` 在每次发起面试时原子性递减（先查后减在同一个连接内完成），减到 0 后拒绝新面试请求。

### interview_sessions

存储每一次面试会话的完整状态。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | TEXT PK | UUID |
| user_id | INTEGER FK | 关联 users |
| title | TEXT | 面试标题，如"后端工程师 模拟面试" |
| target_role | TEXT | 目标岗位 |
| status | TEXT | `preparing` / `active` / `completed` |
| profile_json | TEXT | 发起面试时的完整请求参数（JSON） |
| workflow_state_json | TEXT | LangGraph 工作流的运行时状态（JSON） |
| evaluation_json | TEXT | 面试结束后的评估结果（JSON，可为 NULL） |
| created_at / updated_at | TEXT | ISO 8601 UTC 时间戳 |

`workflow_state_json` 是这张表最重要也最特殊的字段，详见下文。

### messages

存储面试过程中的每一条消息，按序号排列。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | TEXT PK | UUID |
| session_id | TEXT FK | 关联 interview_sessions |
| seq | INTEGER | 消息序号，从 1 开始，同 session 内单调递增 |
| role | TEXT | `assistant` / `user` |
| kind | TEXT | `question` / `answer` / `follow_up` / `closing` |
| content | TEXT | 消息正文 |
| created_at | TEXT | ISO 8601 UTC 时间戳 |
| meta_json | TEXT | 扩展元数据（JSON，当前为空对象） |

`seq` 在插入时通过 `MAX(seq) + 1` 计算，不依赖数据库自增，方便跨环境保持一致的排序语义。

### resumes

存储用户上传并解析后的简历。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | TEXT PK | UUID |
| user_id | INTEGER FK | 关联 users |
| filename | TEXT | 原始文件名 |
| payload_json | TEXT | 全量解析结果（JSON） |
| created_at / updated_at | TEXT | ISO 8601 UTC 时间戳 |

### 索引

```sql
CREATE INDEX idx_sessions_user_updated ON interview_sessions(user_id, updated_at DESC);
CREATE INDEX idx_messages_session_seq  ON messages(session_id, seq ASC);
CREATE INDEX idx_resumes_user_updated  ON resumes(user_id, updated_at DESC);
```

三个索引覆盖了所有高频查询路径：按用户列举会话/简历（带时间排序）、按会话读取消息列表。

---

## JSON 字段的设计取舍

系统大量使用 TEXT 字段存储 JSON，而不是将结构拆成多列。涉及三个字段：`profile_json`、`workflow_state_json`、`payload_json`（简历）、`evaluation_json`。

**为什么这样做：**

- **workflow_state_json** 存储 LangGraph 的运行时状态，包含题目列表、当前题目索引、每道题的对话线程等。这个结构会随功能迭代演化，如果拆列则每次改动都需要迁移表结构。整体存储让工作流状态对数据库透明，schema 变更只影响应用代码。
- **payload_json**（简历）同理，解析字段（highlights、work_experience 等）会随解析能力迭代增减，整体存储更灵活。
- **profile_json** 存储发起面试时的完整请求参数，作为审计快照，不需要按字段查询。

**代价：**

- 无法在数据库层面按字段过滤或排序（例如"找出所有 target_role 为后端工程师的会话"需要全表扫描）
- JSON 字段没有类型约束，字段缺失或类型错误只能在应用层发现
- 读取时需要在应用层反序列化，`_serialize_session` / `_serialize_resume` 承担了这个职责

---

## 连接管理

每次数据库操作都通过 `get_connection()` 上下文管理器获取一个新连接，操作完成后立即关闭：

```python
@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(settings.database_file, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
```

`check_same_thread=False` 允许 FastAPI 的异步线程池访问同一个数据库文件。SQLite 本身的文件锁保证写操作的串行化，不会出现数据损坏，但并发写入时会有锁等待。

没有使用连接池。对于当前的单机低并发场景，每次新建连接的开销可以接受。

---

## 时间戳处理

所有时间戳统一存储为 ISO 8601 UTC 字符串（`datetime.now(timezone.utc).isoformat()`），例如 `2026-05-09T03:12:45.123456+00:00`。

存为字符串而非 SQLite 的 DATETIME 类型，好处是跨平台行为一致，不依赖 SQLite 的时间函数；代价是无法直接用 SQL 做时间范围查询（当前没有这个需求）。

---

## 当前局限性

**并发写入瓶颈**
SQLite 是文件级锁，同一时刻只能有一个写事务。多用户同时发起面试时，写操作会串行排队。对于教学版低并发场景影响不大，但如果用户量增长，这会成为明显瓶颈。

**没有数据库迁移机制**
表结构通过 `CREATE TABLE IF NOT EXISTS` 在启动时创建，但没有版本管理。如果需要修改已有表的字段（加列、改类型），目前只能手动执行 SQL 或删库重建，没有 Alembic 等迁移工具的支持。

**JSON 字段缺乏约束**
`workflow_state_json` 等字段的内部结构完全由应用代码维护，数据库层面没有任何校验。字段格式变更时，历史数据可能与新代码不兼容，需要应用层做兼容处理。

**没有连接池**
每次请求新建连接，在高并发下会有额外开销。当前场景可以接受，但如果切换到 PostgreSQL，连接池是必须的。

**`seq` 的并发安全性**
消息序号通过 `MAX(seq) + 1` 计算，在极端并发下（同一 session 同时插入两条消息）可能产生重复序号。当前业务逻辑不存在这种场景（用户回答是串行的），但这是一个潜在的隐患。

---

## 后续可优化方向

**迁移到 PostgreSQL**
如果需要支持多实例部署或更高并发，PostgreSQL 是自然的替换目标。当前 `Store` 类封装了所有 SQL，切换数据库只需要替换连接层，JSON 字段可以改用 PostgreSQL 原生的 `jsonb` 类型，支持字段级索引和查询。

**引入 Alembic 做迁移管理**
即使继续使用 SQLite，也应该引入迁移工具管理表结构变更，避免手动维护 SQL 脚本。

**连接池**
如果切换到 PostgreSQL，使用 SQLAlchemy 的异步连接池（`asyncpg` + `create_async_engine`）替换当前的同步连接管理。

**`workflow_state_json` 的结构版本化**
在 `workflow_state_json` 内部加一个 `schema_version` 字段，读取时按版本做兼容处理，防止代码升级后历史数据解析失败。

**消息表的归档策略**
长期运行后 `messages` 表会积累大量历史数据。可以考虑按时间分区或将已完成会话的消息归档到冷存储，保持主表查询性能。
