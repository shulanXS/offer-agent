import logging

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from app.api.routes.auth import router as auth_router
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
    allow_headers=["Authorization", "Content-Type", "X-Request-Id"],
    max_age=600,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(auth_router)
api_router.include_router(interview_options_router)
api_router.include_router(interviews_router)
api_router.include_router(learning_router)
api_router.include_router(resumes_router)
app.include_router(api_router)


@app.on_event("startup")
def on_startup() -> None:
    setup_logging()
    init_db()
    if settings.llm_provider in {"anthropic", "claude", "claude_code"}:
        base_url = settings.anthropic_base_url or "https://api.anthropic.com"
        has_key = bool(settings.anthropic_api_key)
    elif settings.llm_provider == "openai":
        base_url = settings.openai_base_url or "https://api.openai.com/v1"
        has_key = bool(settings.openai_api_key)
    elif settings.llm_provider in {"volcengine", "volc", "ark", "huoshan"}:
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
