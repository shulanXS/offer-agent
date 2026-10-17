"""R1: Repository 基类。

集中"连接获取 + 重试包装"两个跨切关注点。所有 repository 继承此类。
具体事务仍然由调用方通过 `app.db.transaction.transaction()` 上下文管理。
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable, Iterator, TypeVar

from app.core.config import settings
from app.db.transaction import with_retry

T = TypeVar("T")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _loads(data: str | None, fallback: Any) -> Any:
    if not data:
        return fallback
    try:
        return json.loads(data)
    except (TypeError, ValueError):
        return fallback


class BaseRepository:
    """所有 repository 的基类。

    职责：
    - 提供 `get_connection()` 上下文（短连接、自动关闭）
    - 提供 `atomic(do_work)` 便捷方法：自动 `with_retry(transaction())`
    - 提供时间戳/JSON 序列化辅助
    """

    def get_connection(self) -> Iterator[sqlite3.Connection]:  # type: ignore[override]
        """R1: 短连接上下文。读路径或无事务需求时使用。"""
        return _get_connection()

    def atomic(self, do_work: Callable[[sqlite3.Connection], T]) -> T:
        """R1+R3: 在 `transaction()` 上下文里跑 `do_work(conn)`，自动 `with_retry` 包装。"""
        from app.db.transaction import transaction

        def _runner() -> T:
            with transaction() as conn:
                return do_work(conn)

        return with_retry(_runner)


@contextmanager
def _get_connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(settings.database_file, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
