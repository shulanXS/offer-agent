"""A5：基于 slowapi 的限流配置。"""
from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


def _key(request: Request) -> str:
    # 优先用 X-Forwarded-For 的第一个 IP（反代场景），否则取直连
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return get_remote_address(request) or "anonymous"


# 进程内内存限流（单机足够；多实例需切到 Redis）
limiter = Limiter(key_func=_key, default_limits=[])


# 各端点限流规则
AUTH_LIMIT = "20/minute"          # 登录/注册：单 IP 60s 内 20 次
LLM_LIMIT = "10/minute"           # LLM 相关端点（plan 生成、回复、评估）：单 IP 60s 内 10 次
UPLOAD_LIMIT = "5/minute"         # 简历上传：单 IP 60s 内 5 次
READ_LIMIT = "60/minute"          # 读端点：单 IP 60s 内 60 次


def rate_limit_exceeded_handler(_request: Request, exc: RateLimitExceeded) -> "JSONResponse":  # type: ignore[name-defined]
    from fastapi.responses import JSONResponse

    from app.core.errors import build_error_payload, ErrorCode

    return JSONResponse(
        status_code=429,
        content=build_error_payload(
            code=ErrorCode.INTERVIEW_QUOTA_EXHAUSTED,
            message=f"请求过于频繁，请稍后重试：{exc.detail}",
        ),
    )
