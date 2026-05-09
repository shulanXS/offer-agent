import asyncio
import json
from typing import AsyncIterator, Iterable

from app.core.config import settings


def format_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def chunk_text(text: str, chunk_size: int | None = None) -> Iterable[str]:
    size = chunk_size or settings.stream_chunk_size
    content = text or ""
    if not content:
        return []
    return [content[index:index + size] for index in range(0, len(content), size)]


async def stream_text(text: str) -> AsyncIterator[str]:
    for chunk in chunk_text(text):
        yield chunk
        await asyncio.sleep(settings.stream_delay_ms / 1000)
