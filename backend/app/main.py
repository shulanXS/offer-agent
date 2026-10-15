import logging

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from app.api.routes.algorithm import router as algorithm_router
from app.api.routes.auth import router as auth_router
from app.api.routes.billing import router as billing_router
from app.api.routes.interview_options import router as interview_options_router
from app.api.routes.interviews import router as interviews_router
from app.api.routes.learning import router as learning_router
from app.api.routes.resumes import router as resumes_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging_utils import setup_logging
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.db.store import init_db


logger = logging.getLogger("uvicorn.error")

app = FastAPI(title=settings.app_name)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
register_exception_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-Id", "Accept-Language"],
    max_age=600,
)


@app.middleware("http")
async def locale_middleware(request: Request, call_next):
    """v1.1: 把客户端的 Accept-Language 落到 request.state.locale（en|zh）。"""
    from app.core.locale import parse_accept_language
    request.state.locale = parse_accept_language(request.headers.get("accept-language"))
    response = await call_next(request)
    response.headers["Content-Language"] = request.state.locale
    return response

api_router = APIRouter(prefix="/api")
api_router.include_router(auth_router)
api_router.include_router(algorithm_router)
api_router.include_router(billing_router)
api_router.include_router(interview_options_router)
api_router.include_router(interviews_router)
api_router.include_router(learning_router)
api_router.include_router(resumes_router)
app.include_router(api_router)


@app.on_event("startup")
def on_startup() -> None:
    setup_logging()

    # 3.1：JWT secret 启动校验
    if settings.app_env == "production":
        if not settings.jwt_secret:
            raise RuntimeError("JWT_SECRET 生产环境必须配置，请设置环境变量")
        if len(settings.jwt_secret) < 32:
            raise RuntimeError(
                f"JWT_SECRET 生产环境密钥长度需 >= 32（当前 {len(settings.jwt_secret)}），请重新生成"
            )
    elif not settings.jwt_secret:
        logger.warning(
            "jwt_secret 未配置，使用空密钥；请设置 JWT_SECRET 环境变量以确保安全"
        )

    init_db()

    # 4.1：LLM provider 启动校验（别名已收敛）
    valid_providers = {"openai", "anthropic", "volcengine"}
    if settings.llm_provider and settings.llm_provider not in valid_providers:
        raise RuntimeError(
            f"LLM_PROVIDER={settings.llm_provider} 不支持，支持：{', '.join(sorted(valid_providers))}"
        )
    if settings.llm_provider == "anthropic":
        base_url = settings.anthropic_base_url or "https://api.anthropic.com"
        has_key = bool(settings.anthropic_api_key)
    elif settings.llm_provider == "openai":
        base_url = settings.openai_base_url or "https://api.openai.com/v1"
        has_key = bool(settings.openai_api_key)
    elif settings.llm_provider == "volcengine":
        base_url = settings.volcengine_base_url
        has_key = bool(settings.volcengine_api_key)
    else:
        base_url = "-"
        has_key = False
    logger.info(
        "LLM config loaded: env_file=%s provider=%s model=%s base_url=%s has_key=%s log_file=%s",
        settings.model_config.get("env_file"),
        settings.llm_provider,
        settings.llm_model or "-",
        base_url,
        has_key,
        settings.log_file,
    )
    logger.info(
        "CORS origins enabled: %s",
        settings.cors_origins,
    )


@app.get("/healthz")
def healthcheck() -> dict:
    return {"status": "ok", "app": settings.app_name}
