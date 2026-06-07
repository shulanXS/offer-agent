import os

import pytest

os.environ["LLM_PROVIDER"] = "openai"
os.environ["LLM_MODEL"] = "gpt-4o-mini"
os.environ.setdefault("OPENAI_API_KEY", "test-key-for-pytest")


@pytest.fixture(autouse=True)
def force_llm_failures_for_fallbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    """测试不调用真实 LLM，统一走规则/模板降级路径。"""
    from app.core.config import settings
    from tests.support.llm_fake import patch_failing_llm_client

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setattr(settings, "llm_provider", "openai", raising=False)
    monkeypatch.setattr(settings, "llm_model", "gpt-4o-mini", raising=False)
    patch_failing_llm_client(monkeypatch)
