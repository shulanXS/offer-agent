"""域 3.1 验证：JWT secret 启动校验。"""
from __future__ import annotations

import importlib
import pytest

from app.core import config as cfg


def test_create_access_token_empty_secret_raises(monkeypatch) -> None:
    monkeypatch.setattr(cfg.settings, "jwt_secret", "")
    import app.core.security as sec_mod
    importlib.reload(sec_mod)
    with pytest.raises(RuntimeError, match="jwt_secret"):
        sec_mod.create_access_token({"sub": "1"})


def test_create_access_token_with_secret_works(monkeypatch) -> None:
    monkeypatch.setattr(cfg.settings, "jwt_secret", "a" * 32)
    import app.core.security as sec_mod
    importlib.reload(sec_mod)
    token = sec_mod.create_access_token({"sub": "1"})
    assert isinstance(token, str)
    assert len(token) > 0
