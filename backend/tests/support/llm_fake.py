"""测试用 LLM 客户端：模拟真实调用失败，触发规则/模板降级路径。"""
from __future__ import annotations

from app.llm.factory import LLMClient

CREATE_LLM_CLIENT_TARGETS = (
    "app.llm.factory.create_llm_client",
    "app.agent.interview.decide.create_llm_client",
    "app.agent.interview.act.create_llm_client",
    "app.agent.interview.opening.create_llm_client",
    "app.agent.interview.evidence.extract.create_llm_client",
    "app.services.interview.topic_summary.create_llm_client",
    "app.agent.interview_planning.agent.create_llm_client",
    "app.services.resume_service.create_llm_client",
)


class FailingLLMClient(LLMClient):
    provider_name = "test"
    model_name = "failing"

    def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        *,
        operation_name: str = "generic",
        trace_id: str = "",
    ) -> str:
        raise RuntimeError("simulated LLM failure for tests")


def patch_failing_llm_client(monkeypatch, client: FailingLLMClient | None = None) -> FailingLLMClient:
    failing_client = client or FailingLLMClient()

    def _create_llm_client(*_args, **_kwargs):
        return failing_client

    for target in CREATE_LLM_CLIENT_TARGETS:
        monkeypatch.setattr(target, _create_llm_client)
    return failing_client
