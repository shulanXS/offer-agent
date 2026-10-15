from app.core.config import settings
from app.core.errors import ErrorCode, raise_app_error
from app.core.security import (
    create_access_token,
    hash_password,
    needs_rehash,
    verify_password,
)
from app.db.store import Store


class AuthService:
    def __init__(self) -> None:
        self.store = Store()

    def register(self, username: str, password: str) -> dict:
        existing_user = self.store.get_user_by_username(username)
        if existing_user:
            raise_app_error(409, ErrorCode.USERNAME_EXISTS, "用户名已存在")
        user = self.store.create_user(
            username=username,
            password_hash=hash_password(password),
            quota_remaining=settings.default_interview_quota,
        )
        return self._build_auth_response(user)

    def login(self, username: str, password: str) -> dict:
        user = self.store.get_user_by_username(username)
        if not user or not verify_password(password, user["password_hash"]):
            raise_app_error(401, ErrorCode.INVALID_CREDENTIALS, "用户名或密码错误")
        # C2：老 hash 惰性升级（不阻塞主流程）
        if needs_rehash(user["password_hash"]):
            try:
                self.store.update_user_password_hash(user["id"], hash_password(password))
            except Exception:
                import logging

                logging.getLogger("uvicorn.error").exception(
                    "password rehash failed: user_id=%s", user["id"]
                )
        return self._build_auth_response(user)

    def get_public_user(self, user_id: int) -> dict:
        user = self.store.get_user_by_id(user_id)
        if not user:
            raise_app_error(404, ErrorCode.USER_NOT_FOUND, "用户不存在")
        return self._serialize_user(user)

    def _build_auth_response(self, user: dict) -> dict:
        return {
            "access_token": create_access_token({"sub": str(user["id"]), "username": user["username"]}),
            "user": self._serialize_user(user),
        }

    @staticmethod
    def _serialize_user(user: dict) -> dict:
        return {
            "id": user["id"],
            "username": user["username"],
            "quota_remaining": user["quota_remaining"],
        }
