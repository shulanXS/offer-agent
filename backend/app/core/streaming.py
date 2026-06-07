import asyncio
import json
from typing import AsyncIterator, Iterable

from app.core.config import settings


def format_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


SSE_RESPONSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def chunk_text(text: str, chunk_size: int | None = None) -> Iterable[str]:
    size = chunk_size or settings.stream_chunk_size
    content = text or ""
    if not content:
        return []
    return [content[index : index + size] for index in range(0, len(content), size)]


async def stream_text(
    text: str,
    *,
    chunk_size: int | None = None,
    delay_ms: int | None = None,
) -> AsyncIterator[str]:
    """对已生成完整文本做分块延迟输出（模拟流式，非 LLM token 级流）。"""
    size = chunk_size or settings.stream_chunk_size
    delay = (delay_ms if delay_ms is not None else settings.stream_delay_ms) / 1000
    for chunk in chunk_text(text, chunk_size=size):
        yield chunk
        await asyncio.sleep(delay)
