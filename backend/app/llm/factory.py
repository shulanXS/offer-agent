import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.logging_utils import log_payload


logger = logging.getLogger("uvicorn.error")


def _extract_json(text: str) -> Any:
    content = (text or "").strip()
    if not content:
        raise ValueError("empty response")
    if "```json" in content:
        content = content.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in content:
        content = content.split("```", 1)[1].split("```", 1)[0].strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", content)
        if not match:
            raise
        return json.loads(match.group(1))


class LLMClient(ABC):
    provider_name: str
    model_name: str

    @abstractmethod
    def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        *,
        operation_name: str = "generic",
        trace_id: str = "",
    ) -> str:
        raise NotImplementedError

    def generate_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
        *,
        operation_name: str = "generic",
        trace_id: str = "",
    ) -> Any:
        response_text = self.generate_text(
            prompt,
            system_prompt,
            operation_name=operation_name,
            trace_id=trace_id,
        )
        try:
            payload = _extract_json(response_text)
        except Exception:
            logger.exception(
                "[trace_id=%s] Failed to parse JSON from LLM response: provider=%s model=%s operation=%s",
                trace_id or "-",
                self.provider_name,
                self.model_name,
                operation_name,
            )
            raise
        log_payload(
            logger,
            logging.INFO,
            f"LLM parsed JSON: provider={self.provider_name} model={self.model_name} operation={operation_name}",
            payload,
            trace_id=trace_id,
        )
        return payload


class MockLLMClient(LLMClient):
    def __init__(self, model_name: str = "mock") -> None:
        self.provider_name = "mock"
        self.model_name = model_name

    def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        *,
        operation_name: str = "generic",
        trace_id: str = "",
    ) -> str:
        raise RuntimeError("mock client should not be called directly")


class LangChainLLMClient(LLMClient):
    def __init__(self, provider_name: str, model_name: str, model: Any) -> None:
        self.provider_name = provider_name
        self.model_name = model_name
        self._model = model

    @staticmethod
    def _normalize_content(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, str):
                    text = block.strip()
                    if text:
                        parts.append(text)
                    continue
                if not isinstance(block, dict):
                    text = str(block).strip()
                    if text:
                        parts.append(text)
                    continue
                block_type = str(block.get("type", "")).strip().lower()
                if block_type == "text":
                    text = str(block.get("text", "")).strip()
                    if text:
                        parts.append(text)
                elif block_type == "tool_result":
                    text = str(block.get("content", "")).strip()
                    if text:
                        parts.append(text)
            return "\n".join(parts).strip()
        return str(content)

    def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        *,
        operation_name: str = "generic",
        trace_id: str = "",
    ) -> str:
        log_payload(
            logger,
            logging.INFO,
            f"LLM request: provider={self.provider_name} model={self.model_name} operation={operation_name}",
            {
                "system_prompt": system_prompt or "",
                "prompt": prompt,
            },
            trace_id=trace_id,
        )
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        try:
            response = self._model.invoke(messages)
        except Exception:
            logger.exception(
                "[trace_id=%s] LLM invoke failed: provider=%s model=%s operation=%s",
                trace_id or "-",
                self.provider_name,
                self.model_name,
                operation_name,
            )
            raise
        text = self._normalize_content(getattr(response, "content", response))
        log_payload(
            logger,
            logging.INFO,
            f"LLM response: provider={self.provider_name} model={self.model_name} operation={operation_name}",
            text,
            trace_id=trace_id,
        )
        return text


def create_llm_client(provider: str | None = None, model_name: str | None = None) -> LLMClient:
    selected_provider = (provider or settings.llm_provider or "mock").strip().lower()
    selected_model = (model_name or settings.llm_model or "").strip()

    if selected_provider in {"mock", ""}:
        return MockLLMClient(selected_model or "mock")

    if selected_provider in {"openai"}:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY 未配置")
        model = ChatOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
            model=selected_model or "gpt-4o-mini",
            temperature=0.2,
            timeout=settings.llm_timeout_seconds,
        )
        return LangChainLLMClient("openai", selected_model or "gpt-4o-mini", model)

    if selected_provider in {"anthropic", "claude", "claude_code"}:
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY 未配置")
        model = ChatAnthropic(
            api_key=settings.anthropic_api_key,
            base_url=settings.anthropic_base_url or None,
            model=selected_model or "claude-3-5-sonnet-20241022",
            temperature=0.2,
            timeout=settings.llm_timeout_seconds,
        )
        return LangChainLLMClient("anthropic", selected_model or "claude-3-5-sonnet-20241022", model)

    if selected_provider in {"volcengine", "volc", "ark", "huoshan"}:
        if not settings.volcengine_api_key:
            raise ValueError("VOLCENGINE_API_KEY 未配置")
        model = ChatOpenAI(
            api_key=settings.volcengine_api_key,
            base_url=settings.volcengine_base_url,
            model=selected_model or "doubao-seed-1-6-flash-250715",
            temperature=0.2,
            timeout=settings.llm_timeout_seconds,
        )
        return LangChainLLMClient("volcengine", selected_model or "doubao-seed-1-6-flash-250715", model)

    raise ValueError(f"不支持的 LLM_PROVIDER: {selected_provider}")
