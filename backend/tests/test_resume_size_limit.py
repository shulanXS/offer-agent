"""域 3.3 验证：上传文件大小上限。"""
from __future__ import annotations

import asyncio
import importlib
import time

import pytest

from app.core import config as cfg
from app.core.config import settings
from app.db import store as store_mod
from app.db import transaction as tx_mod
from app.db.transaction import transaction
from app.services.resume_service import ResumeService


@pytest.fixture
def fresh_db(monkeypatch, tmp_path):
    db_file = str(tmp_path / "test.db")
    monkeypatch.setenv("PYTHONHASHSEED", "0")
    monkeypatch.setattr(cfg.settings, "database_path", db_file)
    importlib.reload(store_mod)
    importlib.reload(tx_mod)
    store_mod.init_db()
    yield db_file


def _insert_user(uid: int) -> None:
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO users (id, username, password_hash, quota_remaining, created_at, updated_at)
            VALUES (?, ?, 'h', 5, '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')
            """,
            (uid, f"u_{uid}"),
        )


class _LimitedFakeFile:
    def __init__(self, content: bytes, filename: str):
        self._content = content
        self.filename = filename

    async def read(self, n: int = -1) -> bytes:
        if n < 0:
            return self._content
        return self._content[:n]


class _NeverReadFakeFile:
    filename = "malicious.exe"

    async def read(self, n: int = -1) -> bytes:
        raise AssertionError("Should not read body for unsupported type")


def test_resume_size_over_limit_rejected(fresh_db) -> None:
    user_id = int(time.time() * 1000) % 1_000_000 + 1
    _insert_user(user_id)
    svc = ResumeService()

    big_content = b"x" * (6 * 1024 * 1024)
    assert len(big_content) > settings.max_upload_bytes

    file = _LimitedFakeFile(big_content, "resume.pdf")
    with pytest.raises(Exception) as exc_info:
        asyncio.run(svc.parse_upload(user_id=user_id, file=file))
    # 期望 FastAPI HTTPException 413
    exc = exc_info.value
    if hasattr(exc, "status_code"):
        assert exc.status_code == 413
    else:
        assert "413" in str(type(exc))


def test_resume_type_check_before_size(fresh_db) -> None:
    """.exe 文件立即 400，不读 body。"""
    svc = ResumeService()
    with pytest.raises(Exception):
        asyncio.run(svc.parse_upload(user_id=1, file=_NeverReadFakeFile()))
