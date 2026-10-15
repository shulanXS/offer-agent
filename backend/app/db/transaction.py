"""SQLite 事务上下文（A1：WAL + 乐观锁 + 串行化写入）。"""
from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable, Iterator, TypeVar

from app.core.config import settings

logger = logging.getLogger("uvicorn.error")

T = TypeVar("T")

# 当 SQLite 报 "database is locked" 时重试的次数
_RETRY_MAX = 5
# 每次重试前指数退避基数（毫秒）
_RETRY_BACKOFF_MS = 50


def _open_conn() -> sqlite3.Connection:
    """建立独立连接（不走 get_connection 避免嵌套事务问题）。"""
    conn = sqlite3.connect(settings.database_file, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """显式事务上下文。

    - 用独立连接（BEGIN IMMEDIATE 不能嵌套于已有连接的自动事务）
    - BEGIN IMMEDIATE 立即获取写锁，避免升级冲突
    - 失败时回滚并抛出
    """
    conn = _open_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except sqlite3.OperationalError:
                logger.exception("rollback failed during transaction")
            raise
    finally:
        conn.close()


def with_retry(func: Callable[[], T]) -> T:
    """执行一个可能因为 lock 失败的写操作，指数退避重试。"""
    import time

    last_exc: Exception | None = None
    for attempt in range(_RETRY_MAX):
        try:
            return func()
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            last_exc = exc
            wait_ms = _RETRY_BACKOFF_MS * (2**attempt)
            logger.warning("sqlite locked, retrying in %sms (attempt=%s)", wait_ms, attempt + 1)
            time.sleep(wait_ms / 1000)
    raise last_exc  # type: ignore[misc]


def optimistic_update(
    conn: sqlite3.Connection,
    *,
    table: str,
    row_id: Any,
    expected_version: int,
    assignments: dict[str, Any],
) -> bool:
    """乐观锁 UPDATE：仅在 version 匹配时更新并 +1。

    返回 True 表示更新成功，False 表示版本已过期（需要重试或放弃）。
    """
    sets = ["updated_at = ?", "version = version + 1"]
    params: list[Any] = [datetime.now(timezone.utc).isoformat()]
    for col, val in assignments.items():
        sets.append(f"{col} = ?")
        params.append(val)
    params.append(row_id)
    params.append(expected_version)
    sql = f"UPDATE {table} SET {', '.join(sets)} WHERE id = ? AND version = ?"
    cursor = conn.execute(sql, tuple(params))
    return cursor.rowcount > 0
