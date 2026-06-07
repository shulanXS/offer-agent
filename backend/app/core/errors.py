from enum import Enum
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging_utils import new_trace_id


class ErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    AUTH_INVALID = "AUTH_INVALID"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    USERNAME_EXISTS = "USERNAME_EXISTS"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    RESUME_NOT_FOUND = "RESUME_NOT_FOUND"
    RESUME_FILE_TYPE_UNSUPPORTED = "RESUME_FILE_TYPE_UNSUPPORTED"
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
    INTERNAL_ERROR = "INTERNAL_ERROR"


def raise_app_error(
    status_code: int,
    code: ErrorCode,
    message: str,
    *,
    trace_id: str = "",
    details: Any = None,
) -> None:
    raise HTTPException(status_code=status_code, detail=build_error_payload(code, message, trace_id=trace_id, details=details))


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
        "trace_id": trace_id or new_trace_id("err"),
    }
    if details is not None:
        payload["details"] = details
    return payload


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and "code" in exc.detail and "message" in exc.detail:
            payload = exc.detail
        else:
            payload = build_error_payload(
                ErrorCode.INTERNAL_ERROR if exc.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR else ErrorCode.VALIDATION_ERROR,
                str(exc.detail),
            )
        return JSONResponse(status_code=exc.status_code, content=payload)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(item) for item in error.get("loc", [])[1:]) or "body",
                "message": error.get("msg", "参数校验失败"),
                "type": error.get("type", "validation_error"),
            }
            for error in exc.errors()
        ]
        payload = build_error_payload(
            ErrorCode.VALIDATION_ERROR,
            "请求参数校验失败",
            details=details,
        )
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=payload)
