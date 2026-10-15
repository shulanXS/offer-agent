"""C2：密码 hash 与 JWT。

- 新用户/被惰性升级的用户：argon2
- 老用户（PBKDF2 12 万轮）：保留可验证；登录成功后惰性 rehash
- 格式：$argon2id$... 为新；$pbkdf2_sha256$... 为旧（不强制迁移历史格式）
"""
from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

from app.core.config import settings


# 惰性升级阈值：旧 hash 验证通过时若属于旧算法，调用方拿到原密码后可触发 rehash
_PBKDF2_ITERATIONS = 120_000
_HASHER = PasswordHasher()  # 默认参数：time_cost=3, memory_cost=64MB, parallelism=4

# 旧 hash 标识前缀（PBKDF2 在 store 里实际为 "salt_hex$digest_hex"，没有前缀）
# 这里通过 hex 长度粗略判定：salt 16 字节 = 32 hex，digest 32 字节 = 64 hex
_OLD_HASH_LEN = 32 + 1 + 64


def hash_password(password: str) -> str:
    """新用户统一用 argon2。"""
    return _HASHER.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """先尝试 argon2，失败再回退 PBKDF2（兼容老数据）。"""
    if not hashed_password:
        return False
    # 1) argon2 路径（新 hash 以 $argon2 开头）
    if hashed_password.startswith("$argon2"):
        try:
            _HASHER.verify(hashed_password, password)
            return True
        except (VerifyMismatchError, InvalidHashError):
            return False
    # 2) PBKDF2 路径（hex$salt$digest 形态：salt_hex$digest_hex）
    if "$" in hashed_password and len(hashed_password) == _OLD_HASH_LEN:
        try:
            salt_hex, digest_hex = hashed_password.split("$", maxsplit=1)
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(digest_hex)
            actual = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS
            )
            return hmac.compare_digest(actual, expected)
        except (ValueError, TypeError):
            return False
    return False


def needs_rehash(hashed_password: str) -> bool:
    """登录成功后判断是否需要把 PBKDF2 升级为 argon2。"""
    if not hashed_password:
        return True
    return not hashed_password.startswith("$argon2")


def create_access_token(payload: Dict[str, Any]) -> str:
    if not settings.jwt_secret:
        raise RuntimeError("jwt_secret 未配置或为空，请设置 JWT_SECRET 环境变量")
    expire_at = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    token_payload = {**payload, "exp": expire_at}
    return jwt.encode(token_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
