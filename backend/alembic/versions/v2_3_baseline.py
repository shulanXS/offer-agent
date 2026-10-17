"""R4 baseline：一次性建表迁移，捕获 init_db 全部 CREATE TABLE/INDEX。

- 不再使用 _ensure_column / _ensure_index：所有列/索引在此 baseline 已固化。
- 这是 down_revision=None 的根迁移；之后任何 schema 变动都开新文件并以
  本文件为 down_revision。
- init_db() 仍保留以兼容非 alembic 路径（pytest 内的 fresh_db fixture），
  但其职责降为"幂等建表兜底"，不再做任何 _ensure_column 修补。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision = "v2_3_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("username", sa.Text, nullable=False, unique=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("quota_remaining", sa.Integer, nullable=False, server_default="5"),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
        sa.Column("tier", sa.Text, nullable=False, server_default="free"),
        sa.Column("subscription_expires_at", sa.Text, nullable=True),
        sa.Column("membership_status", sa.Text, nullable=False, server_default="free"),
    )

    # 2. interview_sessions
    op.create_table(
        "interview_sessions",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("target_role", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("profile_json", sa.Text, nullable=False),
        sa.Column("workflow_state_json", sa.Text, nullable=False),
        sa.Column("evaluation_json", sa.Text, nullable=True),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
        sa.Column("resume_id", sa.Text, nullable=True),
        sa.Column("configuration_json", sa.Text, nullable=True),
        sa.Column("confirmed_plan_id", sa.Text, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="0"),
        sa.Column("request_id", sa.Text, nullable=True),
        sa.Column("paused_at", sa.Text, nullable=True),
        sa.Column("total_paused_seconds", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index(
        "idx_sessions_user_updated",
        "interview_sessions",
        ["user_id", "updated_at"],
    )
    op.create_index(
        "uq_sessions_request_id",
        "interview_sessions",
        ["request_id"],
        unique=True,
    )

    # 3. messages
    op.create_table(
        "messages",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("session_id", sa.Text, sa.ForeignKey("interview_sessions.id"), nullable=False),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("meta_json", sa.Text, nullable=True),
        sa.Column("request_id", sa.Text, nullable=True),
    )
    op.create_index("idx_messages_session_seq", "messages", ["session_id", "seq"])

    # 4. resumes
    op.create_table(
        "resumes",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("filename", sa.Text, nullable=False),
        sa.Column("payload_json", sa.Text, nullable=False),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
    )
    op.create_index("idx_resumes_user_updated", "resumes", ["user_id", "updated_at"])

    # 5. interview_plans
    op.create_table(
        "interview_plans",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("session_id", sa.Text, sa.ForeignKey("interview_sessions.id"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("plan_json", sa.Text, nullable=False),
        sa.Column("candidate_summary_json", sa.Text, nullable=False),
        sa.Column("regeneration_strategy", sa.Text, nullable=True),
        sa.Column("focus_topics_json", sa.Text, nullable=True),
        sa.Column("additional_instruction", sa.Text, nullable=True),
        sa.Column("created_at", sa.Text, nullable=False),
    )
    op.create_index(
        "idx_interview_plans_session_version",
        "interview_plans",
        ["session_id", "version"],
    )

    # 6. user_learning_profiles
    op.create_table(
        "user_learning_profiles",
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("resume_id", sa.Text, nullable=False),
        sa.Column("target_role", sa.Text, nullable=False),
        sa.Column("interview_type", sa.Text, nullable=False),
        sa.Column("profile_json", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
        sa.PrimaryKeyConstraint(
            "user_id", "resume_id", "target_role", "interview_type",
        ),
    )

    # 7. learning_session_outcomes
    op.create_table(
        "learning_session_outcomes",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("resume_id", sa.Text, nullable=False),
        sa.Column("session_id", sa.Text, nullable=False, unique=True),
        sa.Column("target_role", sa.Text, nullable=False),
        sa.Column("interview_type", sa.Text, nullable=False),
        sa.Column("completed_at", sa.Text, nullable=False),
        sa.Column("outcome_json", sa.Text, nullable=False),
        sa.Column("deleted_at", sa.Text, nullable=True),
    )
    op.create_index(
        "idx_learning_outcomes_profile",
        "learning_session_outcomes",
        ["user_id", "resume_id", "target_role", "interview_type", "completed_at"],
    )

    # 8. session_locks（v2.3 schema：lock_key PK）
    op.create_table(
        "session_locks",
        sa.Column("lock_key", sa.Text, primary_key=True),
        sa.Column("session_id", sa.Text, nullable=False),
        sa.Column("lock_type", sa.Text, nullable=False, server_default="session"),
        sa.Column("lock_token", sa.Text, nullable=False),
        sa.Column("expires_at", sa.Text, nullable=False),
        sa.Column("created_at", sa.Text, nullable=False),
    )
    op.create_index("idx_session_locks_session", "session_locks", ["session_id"])

    # 9. quota_audit
    op.create_table(
        "quota_audit",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("delta", sa.Integer, nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("session_id", sa.Text, nullable=True),
        sa.Column("created_at", sa.Text, nullable=False),
    )
    op.create_index("idx_quota_audit_user", "quota_audit", ["user_id", "created_at"])

    # 10. payments
    op.create_table(
        "payments",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("package", sa.Text, nullable=False),
        sa.Column("amount_cents", sa.Integer, nullable=False),
        sa.Column("interviews_granted", sa.Integer, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("completed_at", sa.Text, nullable=True),
        sa.Column("idempotency_key", sa.Text, nullable=True),
    )
    op.create_index(
        "uniq_payments_idem",
        "payments",
        ["user_id", "idempotency_key"],
        unique=True,
        sqlite_where=sa.text("idempotency_key IS NOT NULL"),
    )

    # 11. payment_orders
    op.create_table(
        "payment_orders",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("package", sa.Text, nullable=False),
        sa.Column("amount_cents", sa.Integer, nullable=False),
        sa.Column("provider", sa.Text, nullable=False),
        sa.Column("provider_order_id", sa.Text, nullable=False),
        sa.Column("checkout_url", sa.Text, nullable=True),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("idempotency_key", sa.Text, nullable=True),
        sa.Column("subject", sa.Text, nullable=False),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("paid_at", sa.Text, nullable=True),
        sa.Column("metadata_json", sa.Text, nullable=True),
    )
    op.create_index(
        "idx_payment_orders_user_created",
        "payment_orders",
        ["user_id", "created_at"],
    )
    op.create_index(
        "uniq_payment_orders_idem",
        "payment_orders",
        ["user_id", "idempotency_key"],
        unique=True,
        sqlite_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.create_index(
        "idx_payment_orders_provider",
        "payment_orders",
        ["provider", "provider_order_id"],
    )

    # 12. uniq_messages_request_id
    op.create_index(
        "uniq_messages_request_id",
        "messages",
        ["session_id", "request_id"],
        unique=True,
        sqlite_where=sa.text("request_id IS NOT NULL"),
    )


def downgrade() -> None:
    # 不实现：v2_3_baseline → pre-v2.3 是数据回退，应走 backup-restore。
    pass
