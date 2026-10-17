"""R1: Store facade — 委托到各 repository。

原 `store.py` 1801 行被拆为 `app.db.repositories.*`（9 个文件）。
本文件保留 `Store` 类作为向后兼容 facade：所有方法委托到对应 repo。
"""
from __future__ import annotations

import sqlite3
from typing import Iterator

from app.db.repositories import (
    LearningRepository,
    LockRepository,
    MessageRepository,
    PaymentRepository,
    PlanRepository,
    QuotaRepository,
    ResumeRepository,
    SessionRepository,
    UserRepository,
    _assert_known_column,
)
from app.db.repositories.base import _get_connection


def get_connection() -> Iterator[sqlite3.Connection]:
    """R1 兼容：保留 get_connection() 上下文（直接转交 _get_connection）。"""
    return _get_connection()


def init_db() -> None:
    """R4 简化：纯幂等建表兜底（CREATE TABLE IF NOT EXISTS）。

    不再做 _ensure_column / _ensure_index 修补——所有列/索引已由 alembic
    baseline（v2_3_baseline）固化。init_db 仅作为非 alembic 路径（如 pytest
    fresh_db fixture）的兜底。
    """
    with get_connection() as conn:
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
                updated_at TEXT NOT NULL,
                tier TEXT NOT NULL DEFAULT 'free',
                subscription_expires_at TEXT,
                membership_status TEXT NOT NULL DEFAULT 'free'
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
                resume_id TEXT,
                configuration_json TEXT,
                confirmed_plan_id TEXT,
                version INTEGER NOT NULL DEFAULT 0,
                request_id TEXT,
                paused_at TEXT,
                total_paused_seconds INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE UNIQUE INDEX IF NOT EXISTS uq_sessions_request_id
                ON interview_sessions(request_id) WHERE request_id IS NOT NULL;

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
            CREATE UNIQUE INDEX IF NOT EXISTS uniq_messages_request_id
                ON messages(session_id, request_id) WHERE request_id IS NOT NULL;

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
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_session_locks_session ON session_locks(session_id);

            CREATE TABLE IF NOT EXISTS quota_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                delta INTEGER NOT NULL,
                reason TEXT NOT NULL,
                session_id TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_quota_audit_user ON quota_audit(user_id, created_at);

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

            CREATE UNIQUE INDEX IF NOT EXISTS uniq_payments_idem
                ON payments(user_id, idempotency_key) WHERE idempotency_key IS NOT NULL;

            CREATE TABLE IF NOT EXISTS payment_orders (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                package TEXT NOT NULL,
                amount_cents INTEGER NOT NULL,
                provider TEXT NOT NULL,
                provider_order_id TEXT NOT NULL,
                checkout_url TEXT,
                status TEXT NOT NULL,
                idempotency_key TEXT,
                subject TEXT NOT NULL,
                created_at TEXT NOT NULL,
                paid_at TEXT,
                metadata_json TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_payment_orders_user_created ON payment_orders(user_id, created_at DESC);
            CREATE UNIQUE INDEX IF NOT EXISTS uniq_payment_orders_idem
                ON payment_orders(user_id, idempotency_key) WHERE idempotency_key IS NOT NULL;
            CREATE INDEX IF NOT EXISTS idx_payment_orders_provider ON payment_orders(provider, provider_order_id);
            """
        )
        # R4: 同步 membership_status（幂等 UPDATE）— 新装 DB 也跑一下，把 tier/subscription
        # 反映到 membership_status，确保 status 字段对齐。
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
        conn.commit()


class Store:
    """R1: 薄 facade，方法全部委托到对应 repository。

    新代码推荐直接用 `UserRepository()` / `SessionRepository()` 等。
    老代码 `store = Store(); store.create_user(...)` 仍然工作。
    """

    def __init__(self) -> None:
        self.user_repo = UserRepository()
        self.session_repo = SessionRepository()
        self.message_repo = MessageRepository()
        self.plan_repo = PlanRepository()
        self.resume_repo = ResumeRepository()
        self.lock_repo = LockRepository()
        self.quota_repo = QuotaRepository()
        self.payment_repo = PaymentRepository()
        self.learning_repo = LearningRepository()

    # ===== user_repo 委托 =====
    def create_user(self, username, password_hash, quota_remaining):
        return self.user_repo.create_user(username, password_hash, quota_remaining)

    def get_user_by_username(self, username):
        return self.user_repo.get_user_by_username(username)

    def get_user_by_id(self, user_id):
        return self.user_repo.get_user_by_id(user_id)

    def get_user_with_synced_membership(self, user_id):
        return self.user_repo.get_user_with_synced_membership(user_id)

    def update_user_password_hash(self, user_id, password_hash):
        return self.user_repo.update_user_password_hash(user_id, password_hash)

    def is_subscription_active(self, user):
        return self.user_repo.is_subscription_active(user)

    def effective_quota_remaining(self, user):
        return self.user_repo.effective_quota_remaining(user)

    def sync_subscription_status(self, user_id):
        return self.user_repo.sync_subscription_status(user_id)

    # ===== session_repo 委托 =====
    def create_planning_session(self, **kwargs):
        return self.session_repo.create_planning_session(**kwargs)

    def update_planning_session(self, session_id, **kwargs):
        return self.session_repo.update_planning_session(session_id, **kwargs)

    def get_planning_session(self, user_id, session_id):
        return self.session_repo.get_planning_session(user_id, session_id)

    def get_interview_session_record(self, user_id, session_id):
        return self.session_repo.get_interview_session_record(user_id, session_id)

    def list_v2_session_rows(self, user_id):
        return self.session_repo.list_v2_session_rows(user_id)

    def update_session(self, session_id, **kwargs):
        return self.session_repo.update_session(session_id, **kwargs)

    def update_session_in_conn(self, conn, session_id, **kwargs):
        return self.session_repo.update_session_in_conn(conn, session_id, **kwargs)

    def update_planning_session_in_conn(self, conn, session_id, **kwargs):
        return self.session_repo.update_planning_session_in_conn(conn, session_id, **kwargs)

    # ===== message_repo 委托 =====
    def create_message(self, **kwargs):
        return self.message_repo.create_message(**kwargs)

    def create_message_in_conn(self, conn, **kwargs):
        return self.message_repo.create_message_in_conn(conn, **kwargs)

    def find_message_by_request_id(self, session_id, request_id):
        return self.message_repo.find_message_by_request_id(session_id, request_id)

    def find_message_pair_by_request_id(self, session_id, request_id):
        return self.message_repo.find_message_pair_by_request_id(session_id, request_id)

    def list_messages(self, session_id):
        return self.message_repo.list_messages(session_id)

    # ===== plan_repo 委托 =====
    def create_interview_plan(self, **kwargs):
        return self.plan_repo.create_interview_plan(**kwargs)

    def get_latest_plan(self, session_id):
        return self.plan_repo.get_latest_plan(session_id)

    def list_plans_for_session(self, session_id):
        return self.plan_repo.list_plans_for_session(session_id)

    def update_interview_plan_status(self, plan_id, *, status):
        return self.plan_repo.update_interview_plan_status(plan_id, status=status)

    def get_plan_by_id(self, plan_id):
        return self.plan_repo.get_plan_by_id(plan_id)

    def update_interview_plan_status_in_conn(self, conn, plan_id, *, status):
        return self.plan_repo.update_interview_plan_status_in_conn(conn, plan_id, status=status)

    def create_interview_plan_in_conn(self, conn, **kwargs):
        return self.plan_repo.create_interview_plan_in_conn(conn, **kwargs)

    # ===== resume_repo 委托 =====
    def create_resume(self, **kwargs):
        return self.resume_repo.create_resume(**kwargs)

    def list_resumes(self, user_id):
        return self.resume_repo.list_resumes(user_id)

    def get_resume(self, user_id, resume_id):
        return self.resume_repo.get_resume(user_id, resume_id)

    def delete_resume(self, user_id, resume_id):
        return self.resume_repo.delete_resume(user_id, resume_id)

    # ===== lock_repo 委托 =====
    def acquire_session_lock(self, session_id, **kwargs):
        return self.lock_repo.acquire_session_lock(session_id, **kwargs)

    def release_session_lock(self, session_id, **kwargs):
        return self.lock_repo.release_session_lock(session_id, **kwargs)

    def refresh_session_lock(self, session_id, **kwargs):
        return self.lock_repo.refresh_session_lock(session_id, **kwargs)

    def get_session_lock(self, session_id, **kwargs):
        return self.lock_repo.get_session_lock(session_id, **kwargs)

    def get_session_lock_by_type(self, session_id, lock_type):
        return self.lock_repo.get_session_lock_by_type(session_id, lock_type)

    # ===== quota_repo 委托 =====
    def decrement_quota(self, user_id, **kwargs):
        return self.quota_repo.decrement_quota(user_id, **kwargs)

    def compensate_quota(self, user_id, **kwargs):
        return self.quota_repo.compensate_quota(user_id, **kwargs)

    def audit_outcome_for_session(self, session_id, **kwargs):
        return self.quota_repo.audit_outcome_for_session(session_id, **kwargs)

    def decrement_quota_in_conn(self, conn, user_id, **kwargs):
        return self.quota_repo.decrement_quota_in_conn(conn, user_id, **kwargs)

    def compensate_quota_in_conn(self, conn, user_id, **kwargs):
        return self.quota_repo.compensate_quota_in_conn(conn, user_id, **kwargs)

    # ===== payment_repo 委托 =====
    def record_payment(self, **kwargs):
        return self.payment_repo.record_payment(**kwargs)

    def get_payment(self, payment_id):
        return self.payment_repo.get_payment(payment_id)

    def list_payments_for_user(self, user_id):
        return self.payment_repo.list_payments_for_user(user_id)

    def apply_payment_to_user(self, **kwargs):
        return self.payment_repo.apply_payment_to_user(**kwargs)

    def apply_payment_in_conn(self, conn, **kwargs):
        return self.payment_repo.apply_payment_in_conn(conn, **kwargs)

    def record_payment_in_conn(self, conn, **kwargs):
        return self.payment_repo.record_payment_in_conn(conn, **kwargs)

    def update_order_status_in_conn(self, conn, **kwargs):
        return self.payment_repo.update_order_status_in_conn(conn, **kwargs)

    def create_order(self, **kwargs):
        return self.payment_repo.create_order(**kwargs)

    def get_order(self, order_id):
        return self.payment_repo.get_order(order_id)

    def get_order_for_user(self, order_id, user_id):
        return self.payment_repo.get_order_for_user(order_id, user_id)

    def find_order_by_provider_id(self, provider, provider_order_id):
        return self.payment_repo.find_order_by_provider_id(provider, provider_order_id)

    def _find_order_by_idempotency(self, user_id, key):
        return self.payment_repo._find_order_by_idempotency(user_id, key)

    def update_order_status(self, **kwargs):
        return self.payment_repo.update_order_status(**kwargs)

    def list_orders_for_user(self, user_id):
        return self.payment_repo.list_orders_for_user(user_id)

    # ===== learning_repo 委托 =====
    def insert_learning_outcome(self, **kwargs):
        return self.learning_repo.insert_learning_outcome(**kwargs)

    def update_learning_outcome(self, session_id, **kwargs):
        return self.learning_repo.update_learning_outcome(session_id, **kwargs)

    def get_learning_outcome_by_session(self, session_id):
        return self.learning_repo.get_learning_outcome_by_session(session_id)

    def delete_learning_outcome(self, session_id):
        return self.learning_repo.delete_learning_outcome(session_id)

    def list_learning_outcomes(self, **kwargs):
        return self.learning_repo.list_learning_outcomes(**kwargs)

    def upsert_learning_profile(self, **kwargs):
        return self.learning_repo.upsert_learning_profile(**kwargs)

    def get_learning_profile(self, user_id, resume_id, target_role, interview_type):
        return self.learning_repo.get_learning_profile(user_id, resume_id, target_role, interview_type)
