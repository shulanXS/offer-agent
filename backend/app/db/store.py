import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from app.core.config import settings
from app.core.constants import V2_SESSION_SCHEMA_VERSION


# 4.2：白名单列名映射。任何动态 SQL 都必须经过这张表校验。
_SESSION_UPDATABLE_COLUMNS: dict[str, set[str]] = {
    "interview_sessions": {
        "status",
        "workflow_state_json",
        "evaluation_json",
        "confirmed_plan_id",
        "profile_json",
        "title",
        "target_role",
        "resume_id",
        "configuration_json",
    },
    "interview_plans": {"status"},
    "users": {"quota_remaining", "password_hash", "tier", "subscription_expires_at"},
}


def _assert_known_column(table: str, column: str) -> None:
    allowed = _SESSION_UPDATABLE_COLUMNS.get(table)
    if not allowed or column not in allowed:
        raise ValueError(f"refusing to update non-whitelisted column {table}.{column}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _loads(data: str | None, fallback: Any) -> Any:
    if not data:
        return fallback
    return json.loads(data)


def init_db() -> None:
    with get_connection() as conn:
        # PRAGMA WAL 会返回一行结果，先消费掉再 executescript
        conn.execute("PRAGMA journal_mode=WAL").fetchone()
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                quota_remaining INTEGER NOT NULL DEFAULT 5,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS interview_sessions (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                target_role TEXT NOT NULL,
                status TEXT NOT NULL,
                profile_json TEXT NOT NULL,
                workflow_state_json TEXT NOT NULL,
                evaluation_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                seq INTEGER NOT NULL,
                role TEXT NOT NULL,
                kind TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                meta_json TEXT,
                request_id TEXT,
                FOREIGN KEY(session_id) REFERENCES interview_sessions(id)
            );

            CREATE TABLE IF NOT EXISTS resumes (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_user_updated ON interview_sessions(user_id, updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_messages_session_seq ON messages(session_id, seq ASC);
            CREATE INDEX IF NOT EXISTS idx_resumes_user_updated ON resumes(user_id, updated_at DESC);

            CREATE TABLE IF NOT EXISTS interview_plans (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                status TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                candidate_summary_json TEXT NOT NULL,
                regeneration_strategy TEXT,
                focus_topics_json TEXT,
                additional_instruction TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES interview_sessions(id)
            );

            CREATE INDEX IF NOT EXISTS idx_interview_plans_session_version
                ON interview_plans(session_id, version DESC);

            CREATE TABLE IF NOT EXISTS user_learning_profiles (
                user_id INTEGER NOT NULL,
                resume_id TEXT NOT NULL,
                target_role TEXT NOT NULL,
                interview_type TEXT NOT NULL,
                profile_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (user_id, resume_id, target_role, interview_type)
            );

            CREATE TABLE IF NOT EXISTS learning_session_outcomes (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                resume_id TEXT NOT NULL,
                session_id TEXT NOT NULL UNIQUE,
                target_role TEXT NOT NULL,
                interview_type TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                outcome_json TEXT NOT NULL,
                deleted_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_learning_outcomes_profile
                ON learning_session_outcomes(user_id, resume_id, target_role, interview_type, completed_at ASC);

            CREATE TABLE IF NOT EXISTS session_locks (
                lock_key TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                lock_type TEXT NOT NULL DEFAULT 'session',
                lock_token TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES interview_sessions(id)
            );
            CREATE INDEX IF NOT EXISTS idx_session_locks_session
                ON session_locks(session_id);

            CREATE TABLE IF NOT EXISTS quota_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                delta INTEGER NOT NULL,
                reason TEXT NOT NULL,
                session_id TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_quota_audit_user
                ON quota_audit(user_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS payments (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                package TEXT NOT NULL,
                amount_cents INTEGER NOT NULL,
                interviews_granted INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                idempotency_key TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_payments_user_created
                ON payments(user_id, created_at DESC);

            -- v2.5：真实支付订单表
            -- pending -> paid / failed / cancelled；只有 paid 后才入账（充 quota / 升订阅）
            CREATE TABLE IF NOT EXISTS payment_orders (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                package TEXT NOT NULL,
                amount_cents INTEGER NOT NULL,
                provider TEXT NOT NULL,
                provider_order_id TEXT,
                checkout_url TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                idempotency_key TEXT,
                subject TEXT,
                created_at TEXT NOT NULL,
                paid_at TEXT,
                metadata_json TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """
        )
        _ensure_column(conn, "interview_sessions", "resume_id", "TEXT")
        _ensure_column(conn, "interview_sessions", "configuration_json", "TEXT")
        _ensure_column(conn, "interview_sessions", "confirmed_plan_id", "TEXT")
        _ensure_column(conn, "interview_sessions", "version", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "messages", "request_id", "TEXT")
        # v2.2：充值相关列
        _ensure_column(conn, "users", "tier", "TEXT NOT NULL DEFAULT 'free'")
        _ensure_column(conn, "payments", "idempotency_key", "TEXT")
        _ensure_index(
            conn,
            "payments",
            "uniq_payments_idem",
            "CREATE UNIQUE INDEX uniq_payments_idem "
            "ON payments(user_id, idempotency_key) "
            "WHERE idempotency_key IS NOT NULL",
        )
        _ensure_column(conn, "users", "subscription_expires_at", "TEXT")
        # v2.3：聚合会员状态字段
        # 单一权威源描述用户当前会员身份，避免前/后端各自计算 tier+expires_at
        # 派生状态。详见改进方案 v2.3 §3.1。
        _ensure_column(
            conn,
            "users",
            "membership_status",
            "TEXT NOT NULL DEFAULT 'free'",
        )
        # 老数据回填：订阅未过期 → active_subscription；订阅过期 → expired_subscription；
        # 历史 paid 用户 → paid；其他保持 free。
        conn.execute(
            """
            UPDATE users
            SET membership_status = CASE
                WHEN tier = 'subscription'
                     AND subscription_expires_at IS NOT NULL
                     AND datetime(subscription_expires_at) > datetime('now')
                THEN 'active_subscription'
                WHEN tier = 'subscription' THEN 'expired_subscription'
                WHEN tier = 'paid' THEN 'paid'
                ELSE membership_status
            END
            WHERE membership_status = 'free' AND (tier != 'free' OR subscription_expires_at IS NOT NULL)
            """
        )
        # v2.3: session_locks 升级为 lock_key 主键 + lock_type 列
        # 旧表 PK 是 session_id；新表 PK 是 lock_key。
        # 这里简单做法：检测旧表存在 session_id 列则直接建新表 + 数据迁移。
        _migrate_session_locks_v23(conn)
        _ensure_index(
            conn,
            "messages",
            "uniq_messages_request_id",
            "CREATE UNIQUE INDEX uniq_messages_request_id ON messages(session_id, request_id) WHERE request_id IS NOT NULL",
        )
        _ensure_index(
            conn,
            "payment_orders",
            "idx_payment_orders_user_created",
            "CREATE INDEX idx_payment_orders_user_created ON payment_orders(user_id, created_at DESC)",
        )
        _ensure_index(
            conn,
            "payment_orders",
            "uniq_payment_orders_idem",
            "CREATE UNIQUE INDEX uniq_payment_orders_idem ON payment_orders(user_id, idempotency_key) "
            "WHERE idempotency_key IS NOT NULL",
        )
        _ensure_index(
            conn,
            "payment_orders",
            "idx_payment_orders_provider",
            "CREATE INDEX idx_payment_orders_provider ON payment_orders(provider, provider_order_id)",
        )
        conn.commit()


def _migrate_session_locks_v23(conn: sqlite3.Connection) -> None:
    """v2.3: 把 session_locks 从 (session_id PK) 迁移到 (lock_key PK, lock_type TEXT)。
    旧 session_id 行 lock_type 默认 'session'，lock_key=session_id。
    """
    cols = {row[1] for row in conn.execute("PRAGMA table_info(session_locks)").fetchall()}
    if "lock_key" in cols:
        return
    if "session_id" in cols:
        conn.execute(
            """
            CREATE TABLE session_locks__new (
                lock_key TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                lock_type TEXT NOT NULL DEFAULT 'session',
                lock_token TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO session_locks__new (lock_key, session_id, lock_type, lock_token, expires_at, created_at)
            SELECT session_id, session_id, 'session', lock_token, expires_at, created_at
            FROM session_locks
            """
        )
        conn.execute("DROP TABLE session_locks")
        conn.execute("ALTER TABLE session_locks__new RENAME TO session_locks")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_session_locks_session ON session_locks(session_id)"
        )
    else:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS session_locks (
                lock_key TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                lock_type TEXT NOT NULL DEFAULT 'session',
                lock_token TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_session_locks_session ON session_locks(session_id)"
        )


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    existing = {row[1] for row in rows}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _ensure_index(conn: sqlite3.Connection, table: str, name: str, definition: str) -> None:
    rows = conn.execute(f"PRAGMA index_list({table})").fetchall()
    existing = {row[1] for row in rows}
    if name not in existing:
        conn.execute(definition)


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(settings.database_file, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


class Store:
    def create_user(self, username: str, password_hash: str, quota_remaining: int) -> dict[str, Any]:
        timestamp = _now()
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (username, password_hash, quota_remaining, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (username, password_hash, quota_remaining, timestamp, timestamp),
            )
            conn.commit()
            return self.get_user_by_id(cursor.lastrowid)

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    def get_user_with_synced_membership(self, user_id: int) -> dict[str, Any] | None:
        """v2.3：取用户前先做订阅状态同步。

        - tier='subscription' 且 expires_at 已过 → membership_status='expired_subscription'，tier='free'
        - 其他情况保持

        返回同步后的 user dict（不入库；由 caller 决定是否需要持久化）。
        """
        user = self.get_user_by_id(user_id)
        if not user:
            return None
        return self._sync_membership_in_memory(user)

    def update_user_password_hash(self, user_id: int, password_hash: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                (password_hash, _now(), user_id),
            )
            conn.commit()

    def decrement_quota(
        self,
        user_id: int,
        *,
        session_id: str | None = None,
        reason: str = "interview_activate",
    ) -> dict[str, Any] | None:
        # 3.4：原子扣减 + 写 audit。任何事务外调用都不安全，但保留
        # `with_retry` 包装以容忍 "database is locked"。
        from app.db.transaction import with_retry

        def _do() -> dict[str, Any] | None:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT quota_remaining FROM users WHERE id = ?", (user_id,),
                ).fetchone()
                if not row or row["quota_remaining"] <= 0:
                    return None
                conn.execute(
                    "UPDATE users SET quota_remaining = quota_remaining - 1, updated_at = ? WHERE id = ?",
                    (_now(), user_id),
                )
                conn.execute(
                    """
                    INSERT INTO quota_audit (user_id, delta, reason, session_id, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user_id, -1, reason, session_id, _now()),
                )
                conn.commit()
                user = self.get_user_by_id(user_id)
                return user

        return with_retry(_do)

    def compensate_quota(
        self,
        user_id: int,
        *,
        session_id: str | None = None,
        reason: str = "interview_activate_rollback",
    ) -> dict[str, Any] | None:
        """3.4：补偿 +1。事务外版本，给事务回滚后调用。"""
        from app.db.transaction import with_retry

        def _do() -> dict[str, Any] | None:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT quota_remaining FROM users WHERE id = ?", (user_id,),
                ).fetchone()
                if not row:
                    return None
                conn.execute(
                    "UPDATE users SET quota_remaining = quota_remaining + 1, updated_at = ? WHERE id = ?",
                    (_now(), user_id),
                )
                conn.execute(
                    """
                    INSERT INTO quota_audit (user_id, delta, reason, session_id, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user_id, +1, reason, session_id, _now()),
                )
                conn.commit()
                return self.get_user_by_id(user_id)

        return with_retry(_do)

    def audit_outcome_for_session(
        self, session_id: str, *, reason: str = "auto_compensation"
    ) -> dict[str, Any] | None:
        """3.4：发现"已 decrement 但无 outcome"孤儿记录，触发回滚额度。"""
        from app.db.transaction import with_retry

        def _do() -> dict[str, Any] | None:
            with get_connection() as conn:
                row = conn.execute(
                    """
                    SELECT user_id FROM learning_session_outcomes
                    WHERE session_id = ? AND deleted_at IS NULL
                    """,
                    (session_id,),
                ).fetchone()
                if row is not None:
                    return None
                audit = conn.execute(
                    """
                    SELECT user_id FROM quota_audit
                    WHERE session_id = ? AND delta = -1
                    ORDER BY id DESC LIMIT 1
                    """,
                    (session_id,),
                ).fetchone()
                if not audit:
                    return None
                user_id = int(audit["user_id"])
                conn.execute(
                    "UPDATE users SET quota_remaining = quota_remaining + 1, updated_at = ? WHERE id = ?",
                    (_now(), user_id),
                )
                conn.execute(
                    """
                    INSERT INTO quota_audit (user_id, delta, reason, session_id, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user_id, +1, reason, session_id, _now()),
                )
                conn.commit()
                return self.get_user_by_id(user_id)

        return with_retry(_do)

    def decrement_quota_in_conn(
        self,
        conn: sqlite3.Connection,
        user_id: int,
        *,
        session_id: str | None,
        reason: str,
    ) -> dict[str, Any] | None:
        """3.4：事务内原子扣减 + audit。

        v2.3：以 membership_status='active_subscription' 为无限语义权威，
        跳过扣减（写 0-delta 审计便于追溯）。
        """
        row = conn.execute(
            "SELECT quota_remaining, membership_status, subscription_expires_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            return None
        if self.is_subscription_active(dict(row)):
            conn.execute(
                """
                INSERT INTO quota_audit (user_id, delta, reason, session_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, 0, f"{reason}:subscription_no_op", session_id, _now()),
            )
            return None
        if row["quota_remaining"] <= 0:
            return None
        conn.execute(
            "UPDATE users SET quota_remaining = quota_remaining - 1, updated_at = ? WHERE id = ?",
            (_now(), user_id),
        )
        conn.execute(
            """
            INSERT INTO quota_audit (user_id, delta, reason, session_id, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, -1, reason, session_id, _now()),
        )
        return None  # caller 仍可在事务内调用 get_user_by_id 单独读

    def compensate_quota_in_conn(
        self,
        conn: sqlite3.Connection,
        user_id: int,
        *,
        session_id: str | None,
        reason: str,
    ) -> None:
        """3.4：事务内 +1 补偿。v2.3 订阅有效 → 不补偿。"""
        row = conn.execute(
            "SELECT membership_status, subscription_expires_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            return
        if self.is_subscription_active(dict(row)):
            conn.execute(
                """
                INSERT INTO quota_audit (user_id, delta, reason, session_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, 0, f"{reason}:subscription_no_op", session_id, _now()),
            )
            return
        conn.execute(
            "UPDATE users SET quota_remaining = quota_remaining + 1, updated_at = ? WHERE id = ?",
            (_now(), user_id),
        )
        conn.execute(
            """
            INSERT INTO quota_audit (user_id, delta, reason, session_id, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, +1, reason, session_id, _now()),
        )

    def create_planning_session(
        self,
        *,
        user_id: int,
        title: str,
        target_role: str,
        resume_id: str,
        configuration: dict[str, Any],
    ) -> dict[str, Any]:
        session_id = str(uuid.uuid4())
        timestamp = _now()
        profile = {
            "schema_version": V2_SESSION_SCHEMA_VERSION,
            "resume_id": resume_id,
            "configuration": configuration,
        }
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO interview_sessions (
                    id, user_id, title, target_role, status, profile_json,
                    workflow_state_json, evaluation_json, resume_id, configuration_json,
                    confirmed_plan_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, NULL, ?, ?)
                """,
                (
                    session_id,
                    user_id,
                    title,
                    target_role,
                    "planning",
                    json.dumps(profile, ensure_ascii=False),
                    json.dumps({}, ensure_ascii=False),
                    resume_id,
                    json.dumps(configuration, ensure_ascii=False),
                    timestamp,
                    timestamp,
                ),
            )
            conn.commit()
        return self.get_planning_session(user_id, session_id)

    def update_planning_session(
        self,
        session_id: str,
        *,
        status: str | None = None,
        confirmed_plan_id: str | None = None,
    ) -> None:
        # 1.2/4.2：委托到事务版本。
        from app.db.transaction import with_retry

        def _do() -> None:
            with get_connection() as conn:
                self.update_planning_session_in_conn(
                    conn,
                    session_id,
                    status=status,
                    confirmed_plan_id=confirmed_plan_id,
                )
                conn.commit()

        with_retry(_do)

    def get_planning_session(self, user_id: int, session_id: str) -> dict[str, Any] | None:
        record = self.get_interview_session_record(user_id, session_id)
        if not record:
            return None
        configuration = record.get("configuration")
        if not configuration:
            return None
        return {
            "id": record["id"],
            "user_id": record["user_id"],
            "title": record["title"],
            "target_role": record["target_role"],
            "status": record["status"],
            "resume_id": record.get("resume_id") or configuration.get("resume_id", ""),
            "configuration": configuration,
            "confirmed_plan_id": record.get("confirmed_plan_id"),
            "created_at": record["created_at"],
            "updated_at": record["updated_at"],
        }

    def get_interview_session_record(self, user_id: int, session_id: str) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM interview_sessions WHERE id = ? AND user_id = ?",
                (session_id, user_id),
            ).fetchone()
        if not row:
            return None
        session = dict(row)
        profile = _loads(session.get("profile_json"), {})
        configuration = _loads(session.get("configuration_json"), None)
        if configuration is None and profile.get("schema_version") == V2_SESSION_SCHEMA_VERSION:
            configuration = profile.get("configuration", {})
        if not configuration and profile.get("schema_version") != V2_SESSION_SCHEMA_VERSION:
            return None
        return {
            "id": session["id"],
            "user_id": session["user_id"],
            "title": session["title"],
            "target_role": session["target_role"],
            "status": session["status"],
            "resume_id": session.get("resume_id") or configuration.get("resume_id", ""),
            "configuration": configuration,
            "confirmed_plan_id": session.get("confirmed_plan_id"),
            "workflow_state": _loads(session.get("workflow_state_json"), {}),
            "evaluation": _loads(session.get("evaluation_json"), None),
            "created_at": session["created_at"],
            "updated_at": session["updated_at"],
            "messages": self.list_messages(session_id),
        }

    def create_interview_plan(
        self,
        *,
        session_id: str,
        version: int,
        status: str,
        plan_json: dict[str, Any],
        candidate_summary_json: dict[str, Any],
        regeneration_strategy: str | None = None,
        focus_topics: list[str] | None = None,
        additional_instruction: str | None = None,
    ) -> dict[str, Any]:
        plan_id = str(uuid.uuid4())
        timestamp = _now()
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO interview_plans (
                    id, session_id, version, status, plan_json, candidate_summary_json,
                    regeneration_strategy, focus_topics_json, additional_instruction, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    session_id,
                    version,
                    status,
                    json.dumps(plan_json, ensure_ascii=False),
                    json.dumps(candidate_summary_json, ensure_ascii=False),
                    regeneration_strategy,
                    json.dumps(focus_topics or [], ensure_ascii=False),
                    additional_instruction,
                    timestamp,
                ),
            )
            conn.commit()
        return self.get_plan_by_id(plan_id)

    def get_latest_plan(self, session_id: str) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM interview_plans
                WHERE session_id = ?
                ORDER BY version DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
        return self._serialize_plan(dict(row)) if row else None

    def list_plans_for_session(self, session_id: str) -> list[dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM interview_plans
                WHERE session_id = ?
                ORDER BY version ASC
                """,
                (session_id,),
            ).fetchall()
        return [self._serialize_plan(dict(row)) for row in rows]

    def update_interview_plan_status(self, plan_id: str, *, status: str) -> None:
        with get_connection() as conn:
            conn.execute("UPDATE interview_plans SET status = ? WHERE id = ?", (status, plan_id))
            conn.commit()

    def get_plan_by_id(self, plan_id: str) -> dict[str, Any]:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM interview_plans WHERE id = ?", (plan_id,)).fetchone()
        if not row:
            raise ValueError("plan not found")
        return self._serialize_plan(dict(row))

    @staticmethod
    def _serialize_plan(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "session_id": row["session_id"],
            "version": row["version"],
            "status": row["status"],
            "plan_json": _loads(row["plan_json"], {}),
            "candidate_summary_json": _loads(row["candidate_summary_json"], {}),
            "regeneration_strategy": row.get("regeneration_strategy"),
            "focus_topics": _loads(row.get("focus_topics_json"), []),
            "additional_instruction": row.get("additional_instruction"),
            "created_at": row["created_at"],
        }

    def create_resume(self, *, user_id: int, filename: str, payload: dict[str, Any]) -> dict[str, Any]:
        resume_id = str(uuid.uuid4())
        timestamp = _now()
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO resumes (id, user_id, filename, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (resume_id, user_id, filename, json.dumps(payload, ensure_ascii=False), timestamp, timestamp),
            )
            conn.commit()
        return self.get_resume(user_id, resume_id)

    def update_session(
        self,
        session_id: str,
        *,
        status: str | None = None,
        workflow_state: dict[str, Any] | None = None,
        evaluation: dict[str, Any] | None = None,
    ) -> None:
        # 1.2/4.2：委托到事务版本。SQL 仍由白名单列名映射构建。
        from app.db.transaction import with_retry

        def _do() -> None:
            with get_connection() as conn:
                self.update_session_in_conn(
                    conn,
                    session_id,
                    status=status,
                    workflow_state=workflow_state,
                    evaluation=evaluation,
                )
                conn.commit()

        with_retry(_do)

    # 1.2/4.2：事务版本——通过 `conn` 复用同一连接。SQL 仍然由白名单列名映射构建。
    def _build_session_update(
        self,
        *,
        status: str | None,
        workflow_state: dict[str, Any] | None,
        evaluation: dict[str, Any] | None,
        include_version_bump: bool = True,
    ) -> tuple[str, list[Any]]:
        assignments: list[str] = ["updated_at = ?"]
        params: list[Any] = [_now()]
        if status is not None:
            _assert_known_column("interview_sessions", "status")
            assignments.append("status = ?")
            params.append(status)
        if workflow_state is not None:
            _assert_known_column("interview_sessions", "workflow_state_json")
            assignments.append("workflow_state_json = ?")
            params.append(json.dumps(workflow_state, ensure_ascii=False))
        if evaluation is not None:
            _assert_known_column("interview_sessions", "evaluation_json")
            assignments.append("evaluation_json = ?")
            params.append(json.dumps(evaluation, ensure_ascii=False))
        if include_version_bump:
            assignments.append("version = version + 1")
        sql = "UPDATE interview_sessions SET " + ", ".join(assignments) + " WHERE id = ?"
        return sql, params

    def update_session_in_conn(
        self,
        conn: sqlite3.Connection,
        session_id: str,
        *,
        status: str | None = None,
        workflow_state: dict[str, Any] | None = None,
        evaluation: dict[str, Any] | None = None,
    ) -> None:
        sql, params = self._build_session_update(
            status=status, workflow_state=workflow_state, evaluation=evaluation
        )
        params.append(session_id)
        conn.execute(sql, tuple(params))

    def update_planning_session_in_conn(
        self,
        conn: sqlite3.Connection,
        session_id: str,
        *,
        status: str | None = None,
        confirmed_plan_id: str | None = None,
    ) -> None:
        assignments: list[str] = ["updated_at = ?"]
        params: list[Any] = [_now()]
        if status is not None:
            _assert_known_column("interview_sessions", "status")
            assignments.append("status = ?")
            params.append(status)
        if confirmed_plan_id is not None:
            _assert_known_column("interview_sessions", "confirmed_plan_id")
            assignments.append("confirmed_plan_id = ?")
            params.append(confirmed_plan_id)
        params.append(session_id)
        conn.execute(
            "UPDATE interview_sessions SET " + ", ".join(assignments) + " WHERE id = ?",
            tuple(params),
        )

    def create_interview_plan_in_conn(
        self,
        conn: sqlite3.Connection,
        *,
        session_id: str,
        version: int,
        status: str,
        plan_json: dict[str, Any],
        candidate_summary_json: dict[str, Any],
        regeneration_strategy: str | None = None,
        focus_topics: list[str] | None = None,
        additional_instruction: str | None = None,
    ) -> dict[str, Any]:
        plan_id = str(uuid.uuid4())
        timestamp = _now()
        conn.execute(
            """
            INSERT INTO interview_plans (
                id, session_id, version, status, plan_json, candidate_summary_json,
                regeneration_strategy, focus_topics_json, additional_instruction, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan_id,
                session_id,
                version,
                status,
                json.dumps(plan_json, ensure_ascii=False),
                json.dumps(candidate_summary_json, ensure_ascii=False),
                regeneration_strategy,
                json.dumps(focus_topics or [], ensure_ascii=False),
                additional_instruction,
                timestamp,
            ),
        )
        return {
            "id": plan_id,
            "session_id": session_id,
            "version": version,
            "status": status,
            "plan_json": plan_json,
            "candidate_summary_json": candidate_summary_json,
            "regeneration_strategy": regeneration_strategy,
            "focus_topics": focus_topics or [],
            "additional_instruction": additional_instruction,
            "created_at": timestamp,
        }

    def update_interview_plan_status_in_conn(
        self,
        conn: sqlite3.Connection,
        plan_id: str,
        *,
        status: str,
    ) -> None:
        _assert_known_column("interview_plans", "status")
        conn.execute(
            "UPDATE interview_plans SET status = ? WHERE id = ?", (status, plan_id),
        )

    def create_message_in_conn(
        self,
        conn: sqlite3.Connection,
        *,
        session_id: str,
        role: str,
        kind: str,
        content: str,
        meta: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """1.2/1.3：事务内写消息。先做 (session_id, request_id) 幂等检查。"""
        if request_id:
            row = conn.execute(
                "SELECT * FROM messages WHERE session_id = ? AND request_id = ?",
                (session_id, request_id),
            ).fetchone()
            if row is not None:
                return {
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "seq": row["seq"],
                    "role": row["role"],
                    "kind": row["kind"],
                    "content": row["content"],
                    "created_at": row["created_at"],
                    "meta": _loads(row["meta_json"], {}),
                }
        seq_row = conn.execute(
            "SELECT COALESCE(MAX(seq), 0) AS max_seq FROM messages WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        seq = int(seq_row["max_seq"]) + 1
        message_id = str(uuid.uuid4())
        timestamp = _now()
        conn.execute(
            """
            INSERT INTO messages (id, session_id, seq, role, kind, content, created_at, meta_json, request_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                session_id,
                seq,
                role,
                kind,
                content,
                timestamp,
                json.dumps(meta or {}, ensure_ascii=False),
                request_id,
            ),
        )
        return {
            "id": message_id,
            "session_id": session_id,
            "seq": seq,
            "role": role,
            "kind": kind,
            "content": content,
            "created_at": timestamp,
            "meta": meta or {},
        }

    def acquire_session_lock(
        self,
        session_id: str,
        *,
        lock_token: str,
        ttl_seconds: int,
        lock_type: str = "session",
        lock_key: str | None = None,
    ) -> dict[str, Any] | None:
        """v2.3: 分布式锁，lock_key 形如 '{type}:{session_id}'。

        - 同 token 视为可重入（幂等返回该锁的 expires_at）。
        - 异 token + 未过期 → None（冲突）。
        - 异 token + 已过期 → 抢锁成功。
        """
        now_ts = _now()
        from datetime import datetime, timezone, timedelta

        now_dt = datetime.now(timezone.utc)
        expires_at = (now_dt + timedelta(seconds=ttl_seconds)).isoformat()
        key = lock_key or f"{lock_type}:{session_id}"

        with get_connection() as conn:
            row = conn.execute(
                "SELECT lock_token, expires_at FROM session_locks WHERE lock_key = ?",
                (key,),
            ).fetchone()
            if row is None:
                try:
                    conn.execute(
                        """
                        INSERT INTO session_locks (lock_key, session_id, lock_type, lock_token, expires_at, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (key, session_id, lock_type, lock_token, expires_at, now_ts),
                    )
                    conn.commit()
                except sqlite3.IntegrityError:
                    conn.rollback()
                    fresh = conn.execute(
                        "SELECT lock_token, expires_at FROM session_locks WHERE lock_key = ?",
                        (key,),
                    ).fetchone()
                    if fresh is not None:
                        existing_dt = datetime.fromisoformat(str(fresh["expires_at"]))
                        remaining = max(0, int((existing_dt - now_dt).total_seconds()))
                        return {"locked": True, "remaining_seconds": remaining, "lock_type": lock_type}
                    return {"locked": True, "remaining_seconds": ttl_seconds, "lock_type": lock_type}
                return {"lock_token": lock_token, "expires_at": expires_at, "lock_type": lock_type}
            existing_token = str(row["lock_token"])
            existing_expires = str(row["expires_at"])
            existing_dt = datetime.fromisoformat(existing_expires)
            if existing_token == lock_token or existing_dt <= now_dt:
                conn.execute(
                    """
                    UPDATE session_locks
                    SET lock_token = ?, expires_at = ?, created_at = ?, lock_type = ?
                    WHERE lock_key = ?
                    """,
                    (lock_token, expires_at, now_ts, lock_type, key),
                )
                conn.commit()
                return {"lock_token": lock_token, "expires_at": expires_at, "lock_type": lock_type}
            remaining = max(0, int((existing_dt - now_dt).total_seconds()))
            return {"locked": True, "remaining_seconds": remaining, "lock_type": lock_type}

    def release_session_lock(
        self,
        session_id: str,
        *,
        lock_token: str,
        lock_type: str = "session",
        lock_key: str | None = None,
    ) -> bool:
        key = lock_key or f"{lock_type}:{session_id}"
        with get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM session_locks WHERE lock_key = ? AND lock_token = ?",
                (key, lock_token),
            )
            conn.commit()
            return cursor.rowcount > 0

    def refresh_session_lock(
        self,
        session_id: str,
        *,
        lock_token: str,
        ttl_seconds: int,
        lock_type: str = "session",
        lock_key: str | None = None,
    ) -> bool:
        key = lock_key or f"{lock_type}:{session_id}"
        with get_connection() as conn:
            from datetime import datetime, timezone, timedelta

            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat()
            cursor = conn.execute(
                """
                UPDATE session_locks
                SET expires_at = ?
                WHERE lock_key = ? AND lock_token = ?
                """,
                (expires_at, key, lock_token),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_session_lock(
        self,
        session_id: str,
        *,
        lock_type: str = "session",
        lock_key: str | None = None,
    ) -> dict[str, Any] | None:
        key = lock_key or f"{lock_type}:{session_id}"
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM session_locks WHERE lock_key = ?", (key,),
            ).fetchone()
        return dict(row) if row else None

    def get_session_lock_by_type(
        self, session_id: str, lock_type: str,
    ) -> dict[str, Any] | None:
        """按 lock_type 查锁（兼容旧代码直接用 session_id 查的语义）。"""
        return self.get_session_lock(session_id, lock_type=lock_type)

    def list_resumes(self, user_id: int) -> list[dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute("SELECT * FROM resumes WHERE user_id = ? ORDER BY updated_at DESC", (user_id,)).fetchall()
        return [self._serialize_resume(dict(row)) for row in rows]

    def get_resume(self, user_id: int, resume_id: str) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM resumes WHERE id = ? AND user_id = ?", (resume_id, user_id)).fetchone()
        return self._serialize_resume(dict(row)) if row else None

    def delete_resume(self, user_id: int, resume_id: str) -> bool:
        with get_connection() as conn:
            cursor = conn.execute("DELETE FROM resumes WHERE id = ? AND user_id = ?", (resume_id, user_id))
            conn.commit()
            return cursor.rowcount > 0

    def create_message(
        self,
        *,
        session_id: str,
        role: str,
        kind: str,
        content: str,
        meta: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        # 1.2/1.3：委托事务版本，避免代码分叉。
        from app.db.transaction import with_retry

        def _do() -> dict[str, Any]:
            with get_connection() as conn:
                return self.create_message_in_conn(
                    conn,
                    session_id=session_id,
                    role=role,
                    kind=kind,
                    content=content,
                    meta=meta,
                    request_id=request_id,
                )

        return with_retry(_do)

    def find_message_by_request_id(
        self, session_id: str, request_id: str
    ) -> dict[str, Any] | None:
        """A2 公开接口：按 (session_id, request_id) 查找消息。"""
        return self._find_message_by_request_id(session_id, request_id)

    def find_message_pair_by_request_id(
        self, session_id: str, request_id: str
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """v2.3: 按 (session_id, request_id) 找到 user_message 和其紧邻的下一条 assistant_message。

        关键点：用 seq 配对，避免 `_latest_assistant_message` 拿陈旧消息。
        返回 (user_message, assistant_message)；任一缺失时对应项为 None。
        """
        user = self._find_message_by_request_id(session_id, request_id)
        if not user:
            return None, None
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM messages
                WHERE session_id = ? AND seq = ? AND role = 'assistant'
                """,
                (session_id, int(user["seq"]) + 1),
            ).fetchone()
        if not row:
            return user, None
        return user, {
            "id": row["id"],
            "session_id": row["session_id"],
            "seq": row["seq"],
            "role": row["role"],
            "kind": row["kind"],
            "content": row["content"],
            "created_at": row["created_at"],
            "meta": _loads(row["meta_json"], {}),
        }

    def _find_message_by_request_id(
        self, session_id: str, request_id: str
    ) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM messages
                WHERE session_id = ? AND request_id = ?
                """,
                (session_id, request_id),
            ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "session_id": row["session_id"],
            "seq": row["seq"],
            "role": row["role"],
            "kind": row["kind"],
            "content": row["content"],
            "created_at": row["created_at"],
            "meta": _loads(row["meta_json"], {}),
        }

    def list_messages(self, session_id: str) -> list[dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY seq ASC",
                (session_id,),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "session_id": row["session_id"],
                "seq": row["seq"],
                "role": row["role"],
                "kind": row["kind"],
                "content": row["content"],
                "created_at": row["created_at"],
                "meta": _loads(row["meta_json"], {}),
            }
            for row in rows
        ]

    def list_v2_session_rows(self, user_id: int) -> list[dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, title, target_role, status, workflow_state_json, evaluation_json,
                       configuration_json, created_at, updated_at
                FROM interview_sessions
                WHERE user_id = ?
                  AND configuration_json IS NOT NULL
                  AND TRIM(configuration_json) != ''
                ORDER BY updated_at DESC
                """,
                (user_id,),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "title": row["title"],
                "target_role": row["target_role"],
                "status": row["status"],
                "workflow_state": _loads(row["workflow_state_json"], {}),
                "evaluation": _loads(row["evaluation_json"], None),
                "configuration": _loads(row["configuration_json"], {}),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def insert_learning_outcome(
        self,
        *,
        outcome_id: str,
        user_id: int,
        resume_id: str,
        session_id: str,
        target_role: str,
        interview_type: str,
        completed_at: str,
        outcome_json: dict[str, Any],
    ) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO learning_session_outcomes (
                    id, user_id, resume_id, session_id, target_role, interview_type,
                    completed_at, outcome_json, deleted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    outcome_id,
                    user_id,
                    resume_id,
                    session_id,
                    target_role,
                    interview_type,
                    completed_at,
                    json.dumps(outcome_json, ensure_ascii=False),
                ),
            )
            conn.commit()

    def update_learning_outcome(
        self,
        session_id: str,
        *,
        outcome_json: dict[str, Any],
        completed_at: str,
    ) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE learning_session_outcomes
                SET outcome_json = ?, completed_at = ?
                WHERE session_id = ? AND deleted_at IS NULL
                """,
                (json.dumps(outcome_json, ensure_ascii=False), completed_at, session_id),
            )
            conn.commit()

    def get_learning_outcome_by_session(self, session_id: str) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM learning_session_outcomes
                WHERE session_id = ? AND deleted_at IS NULL
                """,
                (session_id,),
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["outcome_json"] = _loads(data.get("outcome_json"), {})
        return data

    def delete_learning_outcome(self, session_id: str) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE learning_session_outcomes
                SET deleted_at = ?
                WHERE session_id = ? AND deleted_at IS NULL
                """,
                (_now(), session_id),
            )
            conn.commit()

    def list_learning_outcomes(
        self,
        *,
        user_id: int,
        resume_id: str,
        target_role: str,
        interview_type: str,
    ) -> list[dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM learning_session_outcomes
                WHERE user_id = ? AND resume_id = ? AND target_role = ? AND interview_type = ?
                  AND deleted_at IS NULL
                ORDER BY completed_at ASC
                """,
                (user_id, resume_id, target_role, interview_type),
            ).fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            data = dict(row)
            data["outcome_json"] = _loads(data.get("outcome_json"), {})
            results.append(data)
        return results

    def upsert_learning_profile(
        self,
        *,
        user_id: int,
        resume_id: str,
        target_role: str,
        interview_type: str,
        profile_json: dict[str, Any],
    ) -> None:
        timestamp = _now()
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO user_learning_profiles (
                    user_id, resume_id, target_role, interview_type, profile_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, resume_id, target_role, interview_type)
                DO UPDATE SET profile_json = excluded.profile_json, updated_at = excluded.updated_at
                """,
                (
                    user_id,
                    resume_id,
                    target_role,
                    interview_type,
                    json.dumps(profile_json, ensure_ascii=False),
                    timestamp,
                ),
            )
            conn.commit()

    def get_learning_profile(
        self,
        user_id: int,
        resume_id: str,
        target_role: str,
        interview_type: str,
    ) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM user_learning_profiles
                WHERE user_id = ? AND resume_id = ? AND target_role = ? AND interview_type = ?
                """,
                (user_id, resume_id, target_role, interview_type),
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["profile_json"] = _loads(data.get("profile_json"), {})
        return data

    @staticmethod
    def _serialize_resume(row: dict[str, Any]) -> dict[str, Any]:
        payload = _loads(row["payload_json"], {})
        return {
            "id": row["id"],
            "filename": row["filename"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "personal_info": payload.get("personal_info", ""),
            "highlights": payload.get("highlights", []),
            "technical_skills": payload.get("technical_skills", []),
            "resume_text": payload.get("resume_text", ""),
            "work_experience": payload.get("work_experience", []),
            "project_experience": payload.get("project_experience", []),
            "model_provider": payload.get("model_provider", ""),
            "model_name": payload.get("model_name", ""),
        }

    # ------------------------------------------------------------------
    # v2.2 充值 (Billing)
    # ------------------------------------------------------------------
    def record_payment(
        self,
        *,
        payment_id: str,
        user_id: int,
        package: str,
        amount_cents: int,
        interviews_granted: int,
        status: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """记录一笔支付（mock 也走审计表）。

        v2.4：支持 `idempotency_key`，同一 (user, key) 唯一约束；重复提交时
        返回首次支付记录，避免双扣。
        """
        timestamp = _now()
        with get_connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO payments (
                        id, user_id, package, amount_cents, interviews_granted,
                        status, created_at, completed_at, idempotency_key
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payment_id,
                        user_id,
                        package,
                        amount_cents,
                        interviews_granted,
                        status,
                        timestamp,
                        timestamp if status == "succeeded" else None,
                        idempotency_key,
                    ),
                )
                conn.commit()
            except Exception as exc:  # noqa: BLE001
                if idempotency_key and "uniq_payments_idem" in str(exc):
                    existing = self._find_payment_by_idempotency(user_id, idempotency_key)
                    if existing:
                        return existing
                raise
        return self.get_payment(payment_id)

    def _find_payment_by_idempotency(self, user_id: int, key: str) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM payments WHERE user_id = ? AND idempotency_key = ?",
                (user_id, key),
            ).fetchone()
        return dict(row) if row else None

    def get_payment(self, payment_id: str) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()
        return dict(row) if row else None

    def list_payments_for_user(self, user_id: int) -> list[dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM payments WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def apply_payment_to_user(
        self,
        *,
        user_id: int,
        package: str,
        interviews_granted: int,
        subscription_expires_at: str | None,
    ) -> dict[str, Any] | None:
        """v2.3：单事务更新用户 tier / quota / subscription_expires_at / membership_status。

        `package == 'subscription'`：tier='subscription'，membership_status='active_subscription'，
                                     subscription_expires_at 写入；quota 不变。
        `package == 'single'`：quota += interviews_granted；若现 membership_status 是
                                'active_subscription'，保持；否则升级为 'paid'。
        """
        from app.db.transaction import with_retry

        def _do() -> dict[str, Any] | None:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT id, membership_status FROM users WHERE id = ?", (user_id,),
                ).fetchone()
                if not row:
                    return None
                current_status = str(row["membership_status"] or "free")
                if package == "subscription":
                    conn.execute(
                        """
                        UPDATE users SET tier = 'subscription',
                                         membership_status = 'active_subscription',
                                         subscription_expires_at = ?,
                                         updated_at = ?
                        WHERE id = ?
                        """,
                        (subscription_expires_at, _now(), user_id),
                    )
                else:  # single
                    # 仅在「非活跃订阅」时才升级为 paid；订阅期内单包购买只加 quota
                    if current_status == "active_subscription":
                        conn.execute(
                            """
                            UPDATE users SET quota_remaining = quota_remaining + ?,
                                             updated_at = ?
                            WHERE id = ?
                            """,
                            (interviews_granted, _now(), user_id),
                        )
                    else:
                        conn.execute(
                            """
                            UPDATE users SET tier = 'paid',
                                             membership_status = 'paid',
                                             quota_remaining = quota_remaining + ?,
                                             updated_at = ?
                            WHERE id = ?
                            """,
                            (interviews_granted, _now(), user_id),
                        )
                conn.commit()
            return self.get_user_by_id(user_id)

        return with_retry(_do)

    def sync_subscription_status(self, user_id: int) -> dict[str, Any] | None:
        """v2.3：把过期订阅降级为 expired_subscription，清 tier='subscription'。

        在 get_user_by_id 后调用；如发现需要降级，立即持久化并返回最新 user。
        其他情况直接返回原 user。
        """
        from app.db.transaction import with_retry

        user = self.get_user_by_id(user_id)
        if not user:
            return None
        if not self._is_subscription_expired(user):
            return user
        # 需要降级
        def _do() -> dict[str, Any] | None:
            with get_connection() as conn:
                conn.execute(
                    """
                    UPDATE users SET tier = 'free',
                                     membership_status = 'expired_subscription',
                                     updated_at = ?
                    WHERE id = ? AND (
                        membership_status = 'active_subscription'
                        OR tier = 'subscription'
                    )
                    """,
                    (_now(), user_id),
                )
                conn.commit()
            return self.get_user_by_id(user_id)
        return with_retry(_do)

    def _is_subscription_expired(self, user: dict[str, Any]) -> bool:
        """判断订阅是否已过期（与 is_subscription_active 互补）。"""
        if user.get("membership_status") == "active_subscription":
            # 仍按 expires_at 二次校验
            expires_at = user.get("subscription_expires_at")
            if not expires_at:
                return True
            try:
                ts = expires_at.replace("Z", "+00:00")
                return datetime.fromisoformat(ts) <= datetime.now(timezone.utc)
            except (ValueError, TypeError):
                return True
        return False

    def _sync_membership_in_memory(self, user: dict[str, Any]) -> dict[str, Any]:
        """v2.3：内存中同步 membership_status，不入库。供 get_user_with_synced_membership 使用。"""
        if self._is_subscription_expired(user):
            user = dict(user)
            user["membership_status"] = "expired_subscription"
            user["tier"] = "free"
        return user

    def is_subscription_active(self, user: dict[str, Any]) -> bool:
        """v2.3：以 membership_status 为权威，expires_at 仅作二次校验。"""
        if user.get("membership_status") != "active_subscription":
            return False
        expires_at = user.get("subscription_expires_at")
        if not expires_at:
            return False
        try:
            # expires_at 形如 2026-11-15T00:00:00+00:00
            ts = expires_at.replace("Z", "+00:00")
            return datetime.fromisoformat(ts) > datetime.now(timezone.utc)
        except (ValueError, TypeError):
            return False

    def effective_quota_remaining(self, user: dict[str, Any]) -> int | None:
        """v2.3：订阅有效 → None（=无限）；否则返回真实剩余。

        返回 None 由 Pydantic schema / 前端识别为"无限"语义。
        """
        if self.is_subscription_active(user):
            return None
        return int(user.get("quota_remaining", 0))

    # ------------------------------------------------------------------
    # v2.5 真实支付订单 (Payment Orders)
    # ------------------------------------------------------------------
    def create_order(
        self,
        *,
        order_id: str,
        user_id: int,
        package: str,
        amount_cents: int,
        provider: str,
        subject: str,
        idempotency_key: str | None = None,
        provider_order_id: str | None = None,
        checkout_url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """创建一笔支付订单。

        若带 `idempotency_key` 且同 (user, key) 已存在订单则直接返回旧单，
        避免重复下单。pending / paid 状态都视为"已存在"，由调用方决定下一步。
        """
        timestamp = _now()
        with get_connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO payment_orders (
                        id, user_id, package, amount_cents, provider,
                        provider_order_id, checkout_url, status,
                        idempotency_key, subject, created_at, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)
                    """,
                    (
                        order_id,
                        user_id,
                        package,
                        amount_cents,
                        provider,
                        provider_order_id or order_id,
                        checkout_url,
                        idempotency_key,
                        subject,
                        timestamp,
                        json.dumps(metadata or {}, ensure_ascii=False),
                    ),
                )
                conn.commit()
            except Exception as exc:  # noqa: BLE001
                if idempotency_key and "uniq_payment_orders_idem" in str(exc):
                    existing = self._find_order_by_idempotency(user_id, idempotency_key)
                    if existing:
                        return existing
                raise
        return self.get_order(order_id) or {}

    def _find_order_by_idempotency(self, user_id: int, key: str) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM payment_orders WHERE user_id = ? AND idempotency_key = ?",
                (user_id, key),
            ).fetchone()
        return dict(row) if row else None

    def get_order(self, order_id: str) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM payment_orders WHERE id = ?", (order_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_order_for_user(self, order_id: str, user_id: int) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM payment_orders WHERE id = ? AND user_id = ?",
                (order_id, user_id),
            ).fetchone()
        return dict(row) if row else None

    def find_order_by_provider_id(
        self, provider: str, provider_order_id: str
    ) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM payment_orders WHERE provider = ? AND provider_order_id = ?",
                (provider, provider_order_id),
            ).fetchone()
        return dict(row) if row else None

    def update_order_status(
        self,
        *,
        order_id: str,
        status: str,
        paid_at: str | None = None,
    ) -> dict[str, Any] | None:
        """更新订单状态。允许 pending -> paid / failed / cancelled 的状态机。"""
        with get_connection() as conn:
            conn.execute(
                "UPDATE payment_orders SET status = ?, paid_at = COALESCE(?, paid_at) WHERE id = ?",
                (status, paid_at, order_id),
            )
            conn.commit()
        return self.get_order(order_id)

    def list_orders_for_user(self, user_id: int) -> list[dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM payment_orders WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]
