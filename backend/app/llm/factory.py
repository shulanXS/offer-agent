import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.logging_utils import log_payload


logger = logging.getLogger("uvicorn.error")

_SPOKEN_JSON_KEYS = ("message", "follow_up", "transition", "text")


def _strip_fence(content: str) -> str:
    """仅在 content 以 ``` 围栏开头时剥围栏。其它情况原样返回。"""
    text = (content or "").strip()
    if text.startswith("```json"):
        body = text[len("```json"):]
        if "```" in body:
            return body.split("```", 1)[0].strip()
        return body.strip()
    if text.startswith("```"):
        body = text[len("```"):]
        if "```" in body:
            return body.split("```", 1)[0].strip()
        return body.strip()
    return text


def extract_spoken_response(text: str) -> str:
    """2.3：极简版本——原样返回，只剥 ``` 围栏。其它清理交给 prompt 强约束。

    配合 §1.2 删除 opening LLM 改写，输出不洁直接 raise 让上游降级到模板问题。
    """
    return _strip_fence(text or "")


def extract_spoken_message(payload: Any) -> str:
    """2.3：直接读 payload 字段，去除正则。"""
    if not isinstance(payload, dict):
        return ""
    for key in _SPOKEN_JSON_KEYS:
        text = extract_spoken_response(str(payload.get(key) or "").strip())
        if text:
            return text
    return ""


def _looks_like_prompt_template(payload: dict[str, Any]) -> bool:
    focus_points = payload.get("focus_points")
    if isinstance(focus_points, list) and any("最多" in str(item) for item in focus_points):
        return True
    questions = payload.get("questions")
    if not isinstance(questions, list) or not questions:
        return False
    first = questions[0]
    if not isinstance(first, dict):
        return False
    title = str(first.get("title", "")).strip()
    prompt = str(first.get("prompt", "")).strip()
    return title == "题目标题" or prompt == "题目内容"


def _score_json_candidate(payload: Any) -> int:
    if not isinstance(payload, dict):
        return 0
    score = 1
    if _looks_like_prompt_template(payload):
        return 0
    focus_points = payload.get("focus_points")
    if isinstance(focus_points, list) and focus_points:
        score += 10 + len(focus_points)
    questions = payload.get("questions")
    if isinstance(questions, list) and questions:
        score += 20 + len(questions)
    if payload.get("personal_info") is not None:
        score += 15
    for key in _SPOKEN_JSON_KEYS:
        message = payload.get(key)
        if isinstance(message, str) and message.strip():
            score += 40 + min(len(message.strip()), 200)
            break
    return score


def _iter_json_candidates(content: str) -> list[Any]:
    decoder = json.JSONDecoder()
    candidates: list[Any] = []
    idx = 0
    while idx < len(content):
        while idx < len(content) and content[idx].isspace():
            idx += 1
        if idx >= len(content):
            break
        try:
            payload, end = decoder.raw_decode(content, idx)
        except json.JSONDecodeError:
            idx += 1
            continue
        candidates.append(payload)
        idx = end
    return candidates


def _extract_json(text: str) -> Any:
    content = _strip_fence(text or "")

    candidates = _iter_json_candidates(content)
    if candidates:
        best = max(candidates, key=_score_json_candidate)
        if _score_json_candidate(best) > 0:
            return best

    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        if exc.msg == "Extra data":
            payload, _ = json.JSONDecoder().raw_decode(content)
            if isinstance(payload, dict) and _score_json_candidate(payload) > 0:
                return payload
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

    async def stream_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        *,
        operation_name: str = "generic",
        trace_id: str = "",
    ) -> "AsyncIterator[str]":
        """A3：异步流式 LLM 输出，逐 token yield。

        默认实现走同步 `generate_text` 一次性返回（保留 fallback）。
        Provider 支持流时（LangChain chat model 有 astream），子类可重写。
        """
        yield self.generate_text(
            prompt,
            system_prompt,
            operation_name=operation_name,
            trace_id=trace_id,
        )

    def supports_streaming(self) -> bool:
        """是否真正支持流式输出。子类可覆盖。"""
        return False

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
                elif block_type in {"thinking", "reasoning"}:
                    continue
                elif block_type == "tool_result":
                    text = str(block.get("content", "")).strip()
                    if text:
                        parts.append(text)
                elif block.get("text"):
                    text = str(block.get("text", "")).strip()
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
        raw_text = self._normalize_content(getattr(response, "content", response))
        text = extract_spoken_response(raw_text)
        if text != raw_text:
            log_payload(
                logger,
                logging.INFO,
                f"LLM spoken response extracted: provider={self.provider_name} model={self.model_name} operation={operation_name}",
                {"raw": raw_text, "extracted": text},
                trace_id=trace_id,
            )
        log_payload(
            logger,
            logging.INFO,
            f"LLM response: provider={self.provider_name} model={self.model_name} operation={operation_name}",
            text,
            trace_id=trace_id,
        )
        # R6：移除 LLMStreamPatcher dispatch。流式输出由 LangGraph
        # astream_events('on_chat_model_stream') 直接捕获真实 LLM token。
        return text

    def supports_streaming(self) -> bool:
        """ChatOpenAI/ChatAnthropic 都实现了 astream 协议。"""
        return hasattr(self._model, "astream")

    async def stream_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        *,
        operation_name: str = "generic",
        trace_id: str = "",
    ) -> AsyncIterator[str]:
        """A3：真接 LLM 流。

        - 优先走 LangChain `model.astream` 拿 token 级 delta
        - 失败/不支持时降级到 `generate_text` 一次性返回
        """
        log_payload(
            logger,
            logging.INFO,
            f"LLM stream request: provider={self.provider_name} model={self.model_name} operation={operation_name}",
            {"system_prompt": system_prompt or "", "prompt": prompt},
            trace_id=trace_id,
        )
        if not self.supports_streaming():
            text = self.generate_text(
                prompt,
                system_prompt,
                operation_name=operation_name,
                trace_id=trace_id,
            )
            if text:
                yield text
            return

        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))

        full_text_parts: list[str] = []
        try:
            async for chunk in self._model.astream(messages):
                content = getattr(chunk, "content", None)
                if content is None:
                    continue
                if isinstance(content, str):
                    delta = content
                elif isinstance(content, list):
                    delta = self._normalize_content(content)
                else:
                    delta = str(content)
                if not delta:
                    continue
                full_text_parts.append(delta)
                yield delta
        except Exception:
            logger.exception(
                "[trace_id=%s] LLM stream failed: provider=%s model=%s operation=%s",
                trace_id or "-",
                self.provider_name,
                self.model_name,
                operation_name,
            )
            # 降级到同步调用
            text = self.generate_text(
                prompt,
                system_prompt,
                operation_name=operation_name,
                trace_id=trace_id,
            )
            if text and not full_text_parts:
                yield text
            return

        full_text = "".join(full_text_parts)
        log_payload(
            logger,
            logging.INFO,
            f"LLM stream done: provider={self.provider_name} model={self.model_name} operation={operation_name}",
            {"len": len(full_text), "preview": full_text[:200]},
            trace_id=trace_id,
        )


def create_llm_client(provider: str | None = None, model_name: str | None = None) -> LLMClient:
    selected_provider = (provider or settings.llm_provider or "").strip().lower()
    selected_model = (model_name or settings.llm_model or "").strip()

    if selected_provider == "mock":
        raise ValueError("LLM_PROVIDER=mock 已废弃，请配置 openai、anthropic 或 volcengine")
    if not selected_provider:
        raise ValueError("LLM_PROVIDER 未配置")

    if selected_provider == "openai":
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

    if selected_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY 未配置")
        anthropic_kwargs: dict[str, Any] = {
            "api_key": settings.anthropic_api_key,
            "base_url": settings.anthropic_base_url or None,
            "model": selected_model or "claude-3-5-sonnet-20241022",
            "temperature": 0.2,
            "timeout": settings.llm_timeout_seconds,
            "max_tokens": 4096,
        }
        if settings.anthropic_base_url:
            anthropic_kwargs["default_headers"] = {
                "Authorization": f"Bearer {settings.anthropic_api_key}",
            }
        model = ChatAnthropic(**anthropic_kwargs)
        return LangChainLLMClient("anthropic", selected_model or "claude-3-5-sonnet-20241022", model)

    if selected_provider == "volcengine":
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

    raise ValueError(f"不支持的 LLM_PROVIDER: {selected_provider}（支持：openai、anthropic、volcengine）")
