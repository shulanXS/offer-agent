"""v2.3 进程内 asyncio pub/sub 事件总线。

单进程 FastAPI 部署前提下，向订阅者推送领域事件（典型用途：评估完成）。
每个 channel 由若干 asyncio.Queue 组成；订阅时创建队列，发布时 fan-out。

注意：
- 进程内单点；多 worker 部署需换 Redis Streams。
- 订阅者需自行 cancel 队列以避免泄漏。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any
from weakref import WeakSet

logger = logging.getLogger("uvicorn.error")


class EventBus:
    def __init__(self) -> None:
        self._channels: dict[str, WeakSet[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, channel: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=128)
        async with self._lock:
            subs = self._channels.get(channel)
            if subs is None:
                subs = WeakSet()
                self._channels[channel] = subs
            subs.add(q)
        return q

    async def unsubscribe(self, channel: str, q: asyncio.Queue) -> None:
        async with self._lock:
            subs = self._channels.get(channel)
            if subs is not None:
                subs.discard(q)

    async def publish(self, channel: str, event: dict[str, Any]) -> None:
        # 不持锁 push，避免订阅慢时阻塞
        subs = self._channels.get(channel)
        if not subs:
            return
        for q in list(subs):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # 背压：丢掉最早事件
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except Exception:  # pragma: no cover
                    logger.warning("event bus publish dropped", exc_info=True)

    def publish_nowait(self, channel: str, event: dict[str, Any]) -> None:
        """同步发布：用于非 asyncio 上下文（如 BackgroundTasks 之后）。"""
        subs = self._channels.get(channel)
        if not subs:
            return
        for q in list(subs):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except Exception:  # pragma: no cover
                    logger.warning("event bus publish_nowait dropped", exc_info=True)


bus = EventBus()


# 工具函数
def evaluation_channel(session_id: str) -> str:
    return f"evaluation:{session_id}"
