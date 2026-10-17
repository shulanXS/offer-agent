"""4.3 v2.1 初始迁移：补齐 v2.1 引入的新列与新表。

- interview_sessions.version 列
- interview_sessions.request_id 列 + 唯一索引
- interview_sessions.paused_at 列
- interview_sessions.total_paused_seconds 列
- session_locks 表
- quota_audit 表

注意：升级幂等——已存在则跳过。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision = "v2_1_initial"
down_revision = "v2_3_baseline"
branch_labels = None
depends_on = None


def _column_exists(conn, table: str, column: str) -> bool:
    rows = conn.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()
    return any(row[1] == column for row in rows)


def _table_exists(conn, table: str) -> bool:
    row = conn.execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
        {"t": table},
    ).fetchone()
    return row is not None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. interview_sessions 新列
    if not _column_exists(conn, "interview_sessions", "version"):
        op.add_column(
            "interview_sessions",
            sa.Column("version", sa.Integer, nullable=False, server_default="0"),
        )
    if not _column_exists(conn, "interview_sessions", "request_id"):
        op.add_column("interview_sessions", sa.Column("request_id", sa.Text, nullable=True))
        op.create_index(
            "uq_sessions_request_id",
            "interview_sessions",
            ["request_id"],
            unique=True,
        )
    if not _column_exists(conn, "interview_sessions", "paused_at"):
        op.add_column("interview_sessions", sa.Column("paused_at", sa.Text, nullable=True))
    if not _column_exists(conn, "interview_sessions", "total_paused_seconds"):
        op.add_column(
            "interview_sessions",
            sa.Column("total_paused_seconds", sa.Integer, nullable=False, server_default="0"),
        )

    # 2. session_locks 表
    if not _table_exists(conn, "session_locks"):
        op.create_table(
            "session_locks",
            sa.Column("session_id", sa.Text, primary_key=True),
            sa.Column("lock_token", sa.Text, nullable=False),
            sa.Column("expires_at", sa.Text, nullable=False),
        )

    # 3. quota_audit 表
    if not _table_exists(conn, "quota_audit"):
        op.create_table(
            "quota_audit",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer, nullable=False),
            sa.Column("delta", sa.Integer, nullable=False),
            sa.Column("reason", sa.Text, nullable=False),
            sa.Column("session_id", sa.Text, nullable=True),
            sa.Column("created_at", sa.Text, nullable=False),
        )
        op.create_index(
            "idx_quota_audit_user",
            "quota_audit",
            ["user_id", "created_at"],
        )


def downgrade() -> None:
    # 仅作为占位；不实现 downgrade（v2.1 → 旧版是数据回退，应走 backup-restore）
    pass
