from enum import Enum
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging_utils import new_trace_id


# v1.1: i18n 双语消息。前端翻译失败时仍可作为兜底。
# message_zh 给中文，message_en 给英文（其余 locale 走 en）。
_DEFAULT_ZH = "请求处理失败"
_DEFAULT_EN = "Request failed"


class ErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    AUTH_INVALID = "AUTH_INVALID"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    USERNAME_EXISTS = "USERNAME_EXISTS"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    RESUME_NOT_FOUND = "RESUME_NOT_FOUND"
    RESUME_FILE_TYPE_UNSUPPORTED = "RESUME_FILE_TYPE_UNSUPPORTED"
    RESUME_TOO_LARGE = "RESUME_TOO_LARGE"
    RESUME_TEXT_TOO_SHORT = "RESUME_TEXT_TOO_SHORT"
    RESUME_PARSE_FAILED = "RESUME_PARSE_FAILED"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    SESSION_ALREADY_COMPLETED = "SESSION_ALREADY_COMPLETED"
    SESSION_NOT_ACTIVE = "SESSION_NOT_ACTIVE"
    INTERVIEW_INPUT_INVALID = "INTERVIEW_INPUT_INVALID"
    INTERVIEW_CONFIG_INVALID = "INTERVIEW_CONFIG_INVALID"
    INTERVIEW_QUOTA_EXHAUSTED = "INTERVIEW_QUOTA_EXHAUSTED"
    MODEL_CONFIG_INVALID = "MODEL_CONFIG_INVALID"
    INTERVIEW_BOOTSTRAP_FAILED = "INTERVIEW_BOOTSTRAP_FAILED"
    INTERVIEW_REPLY_FAILED = "INTERVIEW_REPLY_FAILED"
    INTERVIEW_REPLY_IN_PROGRESS = "INTERVIEW_REPLY_IN_PROGRESS"
    INTERVIEW_EVALUATION_FAILED = "INTERVIEW_EVALUATION_FAILED"
    PLAN_GENERATION_FAILED = "PLAN_GENERATION_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# i18n key 映射（前端按 errors.<key> 在词条文件里查）
_ERROR_I18N_KEY: dict[ErrorCode, str] = {
    ErrorCode.VALIDATION_ERROR: "VALIDATION_ERROR",
    ErrorCode.AUTH_REQUIRED: "AUTH_REQUIRED",
    ErrorCode.AUTH_INVALID: "AUTH_INVALID",
    ErrorCode.USER_NOT_FOUND: "USER_NOT_FOUND",
    ErrorCode.USERNAME_EXISTS: "USERNAME_EXISTS",
    ErrorCode.INVALID_CREDENTIALS: "INVALID_CREDENTIALS",
    ErrorCode.RESUME_NOT_FOUND: "RESUME_NOT_FOUND",
    ErrorCode.RESUME_FILE_TYPE_UNSUPPORTED: "RESUME_FILE_TYPE_UNSUPPORTED",
    ErrorCode.RESUME_TOO_LARGE: "RESUME_TOO_LARGE",
    ErrorCode.RESUME_TEXT_TOO_SHORT: "RESUME_TEXT_TOO_SHORT",
    ErrorCode.RESUME_PARSE_FAILED: "RESUME_PARSE_FAILED",
    ErrorCode.SESSION_NOT_FOUND: "SESSION_NOT_FOUND",
    ErrorCode.SESSION_ALREADY_COMPLETED: "SESSION_ALREADY_COMPLETED",
    ErrorCode.SESSION_NOT_ACTIVE: "SESSION_NOT_ACTIVE",
    ErrorCode.INTERVIEW_INPUT_INVALID: "INTERVIEW_INPUT_INVALID",
    ErrorCode.INTERVIEW_CONFIG_INVALID: "INTERVIEW_CONFIG_INVALID",
    ErrorCode.INTERVIEW_QUOTA_EXHAUSTED: "INTERVIEW_QUOTA_EXHAUSTED",
    ErrorCode.MODEL_CONFIG_INVALID: "MODEL_CONFIG_INVALID",
    ErrorCode.INTERVIEW_BOOTSTRAP_FAILED: "INTERVIEW_BOOTSTRAP_FAILED",
    ErrorCode.INTERVIEW_REPLY_FAILED: "INTERVIEW_REPLY_FAILED",
    ErrorCode.INTERVIEW_REPLY_IN_PROGRESS: "INTERVIEW_REPLY_IN_PROGRESS",
    ErrorCode.INTERVIEW_EVALUATION_FAILED: "INTERVIEW_EVALUATION_FAILED",
    ErrorCode.PLAN_GENERATION_FAILED: "PLAN_GENERATION_FAILED",
    ErrorCode.INTERNAL_ERROR: "INTERNAL_ERROR",
}


def _resolve_locale(request: Request | None) -> str:
    from app.core.locale import DEFAULT as DEFAULT_LOCALE, SUPPORTED
    if request is None:
        return DEFAULT_LOCALE
    locale = getattr(request.state, "locale", None)
    return locale if locale in SUPPORTED else DEFAULT_LOCALE


def _localized_message(code: ErrorCode, request: Request | None) -> tuple[str, str | None]:
    """根据 request locale 选 zh/en 消息；同时返回 i18n_key 供前端二次翻译。"""
    zh = _DEFAULT_ZH
    en = _DEFAULT_EN
    i18n_key = _ERROR_I18N_KEY.get(code)
    # 这里目前用默认占位。实际项目里可由具体 service 调
    # `raise_app_error` 时通过 details 传入更具体的中英文。
    if request is not None and i18n_key is not None:
        return (zh if _resolve_locale(request) == "zh" else en), i18n_key
    return (en if _resolve_locale(request) == "en" else zh), i18n_key


def raise_app_error(
    status_code: int,
    code: ErrorCode,
    message: str,
    *,
    trace_id: str = "",
    details: Any = None,
) -> None:
    raise HTTPException(
        status_code=status_code,
        detail=build_error_payload(code, message, trace_id=trace_id, details=details),
    )


class PlanGenerationRetryableError(Exception):
    """F4: LLM 生成计划失败但可重试。携带结构化信息给前端展示「换个模型重试」。"""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = True,
        fallback_provider: str | None = None,
        fallback_model: str | None = None,
    ):
        super().__init__(message)
        self.retryable = retryable
        self.fallback_provider = fallback_provider
        self.fallback_model = fallback_model

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": ErrorCode.PLAN_GENERATION_FAILED.value,
            "message": str(self),
            "retryable": self.retryable,
            "fallback_model": self.fallback_model,
            "fallback_provider": self.fallback_provider,
        }


def build_error_payload(
    code: ErrorCode,
    message: str,
    *,
    trace_id: str = "",
    details: Any = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code.value,
        "message": message,
        "i18n_key": _ERROR_I18N_KEY.get(code),
        "trace_id": trace_id or new_trace_id("err"),
    }
    if details is not None:
        payload["details"] = details
    return payload


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(PlanGenerationRetryableError)
    async def plan_retryable_handler(
        request: Request, exc: PlanGenerationRetryableError
    ) -> JSONResponse:
        # v1.1 F4: surface structured retryable error inline (no HTTP error).
        # Frontend uses retryable_error.retryable to show the "retry" button.
        return JSONResponse(
            status_code=200,
            content={"retryable_error": exc.to_dict()},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and "code" in exc.detail and "message" in exc.detail:
            payload = exc.detail
        else:
            code = (
                ErrorCode.INTERNAL_ERROR
                if exc.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR
                else ErrorCode.VALIDATION_ERROR
            )
            payload = build_error_payload(code, str(exc.detail))
        # locale 化 message（仅当 payload 仍是默认占位时）
        if "code" in payload and "message" in payload:
            try:
                code_enum = ErrorCode(payload["code"])
                msg, key = _localized_message(code_enum, request)
                # 若原 message 是非空且不是占位，保留；否则用本地化
                if not payload.get("message") or payload.get("message") in (_DEFAULT_ZH, _DEFAULT_EN):
                    payload["message"] = msg
                if not payload.get("i18n_key") and key:
                    payload["i18n_key"] = key
            except ValueError:
                pass
        return JSONResponse(status_code=exc.status_code, content=payload)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(item) for item in error.get("loc", [])[1:]) or "body",
                "message": error.get("msg", "validation error"),
                "type": error.get("type", "validation_error"),
            }
            for error in exc.errors()
        ]
        locale = _resolve_locale(request)
        payload = build_error_payload(
            ErrorCode.VALIDATION_ERROR,
            "请求参数校验失败" if locale == "zh" else "Request validation failed",
            details=details,
        )
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=payload)
