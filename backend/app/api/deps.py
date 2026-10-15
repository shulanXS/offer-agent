import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import ErrorCode, raise_app_error
from app.core.locale import DEFAULT as DEFAULT_LOCALE, SUPPORTED
from app.core.security import decode_access_token
from app.db.store import Store


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
    if credentials is None:
        raise_app_error(401, ErrorCode.AUTH_REQUIRED, "缺少登录凭证")

    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise_app_error(401, ErrorCode.AUTH_INVALID, "登录状态已失效", details={"reason": str(exc.__class__.__name__)})

    user_id = int(payload["sub"])
    user = Store().get_user_by_id(user_id)
    if not user:
        raise_app_error(401, ErrorCode.USER_NOT_FOUND, "用户不存在")
    return user


def get_locale(request: Request) -> str:
    """v1.1: 取 Accept-Language 解析后的 locale（en|zh）。"""
    locale = getattr(request.state, "locale", None)
    if locale in SUPPORTED:
        return locale
    return DEFAULT_LOCALE
