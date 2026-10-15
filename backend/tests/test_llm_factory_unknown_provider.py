"""域 4.1 验证：LLM 工厂别名集收敛。"""
from __future__ import annotations

import importlib

import pytest

from app.llm.factory import create_llm_client


@pytest.mark.parametrize(
    "alias",
    [
        "claude",
        "claude_code",
        "volc",
        "ark",
        "huoshan",
        "openai_compat",
        "unknown_provider",
    ],
)
def test_create_llm_client_unknown_provider_raises(alias: str) -> None:
    """任何非标准名（含历史别名）都应抛错，明确告诉用户用哪个名字。"""
    with pytest.raises(ValueError) as exc:
        create_llm_client(provider=alias)
    message = str(exc.value)
    # 错误信息应明确列出合法值
    assert "不支持" in message
    assert "openai" in message and "anthropic" in message and "volcengine" in message


def test_create_llm_client_empty_provider_raises(monkeypatch) -> None:
    """settings.llm_provider 留空时也抛错。"""
    from app.core import config as cfg
    from app.llm import factory as factory_mod

    # 重置 settings + factory，避免之前测试的 reload 影响
    importlib.reload(cfg)
    importlib.reload(factory_mod)
    monkeypatch.setattr(cfg.settings, "llm_provider", "")
    with pytest.raises(ValueError, match="LLM_PROVIDER 未配置"):
        factory_mod.create_llm_client(provider=None)
