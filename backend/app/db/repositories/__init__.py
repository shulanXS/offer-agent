"""R1: Repository 集合。

所有表 / 主题的 SQL 都在这里。`app.db.store.Store` 退化为 facade，
仅作向后兼容。
"""
from app.db.repositories.base import BaseRepository
from app.db.repositories.learning_repo import LearningRepository
from app.db.repositories.lock_repo import LockRepository
from app.db.repositories.message_repo import MessageRepository
from app.db.repositories.payment_repo import PaymentRepository
from app.db.repositories.plan_repo import PlanRepository
from app.db.repositories.quota_repo import QuotaRepository
from app.db.repositories.resume_repo import ResumeRepository
from app.db.repositories.session_repo import SessionRepository, _assert_known_column
from app.db.repositories.user_repo import UserRepository

__all__ = [
    "BaseRepository",
    "LearningRepository",
    "LockRepository",
    "MessageRepository",
    "PaymentRepository",
    "PlanRepository",
    "QuotaRepository",
    "ResumeRepository",
    "SessionRepository",
    "UserRepository",
    "_assert_known_column",
]
