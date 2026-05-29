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

_REASONING_MARKERS = (
    "让我分析一下",
    "用户要求我",
    "我需要生成",
    "让我写一个自然的追问",
    "让我思考一下",
    "最终版本",
    "追问方向提示",
    "字数：",
    "符合要求",
    "上一轮回答",
)

_SPOKEN_OUTPUT_MARKERS = (
    "最终版本：",
    "最终版本:",
    "让我写一个自然的追问：",
    "让我写一个自然的追问:",
    "比如：",
    "比如:",
    "例如：",
    "例如:",
)

_META_LINE_PATTERNS = (
    re.compile(r"^用户要求"),
    re.compile(r"^让我分析"),
    re.compile(r"^我需要"),
    re.compile(r"^考虑到"),
    re.compile(r"^由于题目"),
    re.compile(r"^要求[：:]"),
    re.compile(r"^追问方向"),
    re.compile(r"^上一轮回答"),
    re.compile(r"^这个追问"),
    re.compile(r"^或者可以"),
    re.compile(r"^让我再调整"),
    re.compile(r"^让我数一下"),
    re.compile(r"字数"),
    re.compile(r"符合要求"),
    re.compile(r"^可以追问"),
    re.compile(r"^我觉得"),
    re.compile(r"^我会问"),
    re.compile(r"^我选择"),
    re.compile(r"^- "),
    re.compile(r"^\d+\.\s"),
)

_SPOKEN_JSON_KEYS = ("message", "follow_up", "transition", "text")


def _looks_like_reasoning_output(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return False
    if any(marker in stripped for marker in _REASONING_MARKERS):
        return True
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    bullet_count = sum(1 for line in lines if line.startswith("- "))
    return bullet_count >= 3 and len(lines) >= 5


def _strip_wrapping_quotes(text: str) -> str:
    text = text.strip()
    for open_quote, close_quote in (('"', '"'), ("“", "”"), ("'", "'"), ("「", "」")):
        if text.startswith(open_quote) and text.endswith(close_quote) and len(text) > 2:
            return text[len(open_quote) : -len(close_quote)].strip()
    return text


def _is_meta_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    return any(pattern.search(stripped) for pattern in _META_LINE_PATTERNS)


def _collect_spoken_candidates(text: str) -> list[str]:
    candidates: list[str] = []

    for match in re.finditer(r'["“]([^"”]{12,})["”]', text):
        part = match.group(1).strip()
        if part and not _is_meta_line(part):
            candidates.append(part)

    for raw_line in text.splitlines():
        line = raw_line.strip()
        for segment in re.split(r'["”\'」]\s+(?=[\u4e00-\u9fff好的您你请])', line):
            segment = _strip_wrapping_quotes(segment.strip())
            if not segment:
                continue
            for part in re.split(r"(?<=[。！？?])\s+", segment):
                part = _strip_wrapping_quotes(part.strip())
                if part and not _is_meta_line(part) and len(part) >= 12:
                    candidates.append(part)

    if candidates:
        return candidates

    cleaned = _strip_wrapping_quotes(re.sub(r"\s+", " ", text).strip())
    for part in re.split(r"(?<=[。！？?])\s+", cleaned):
        part = _strip_wrapping_quotes(part.strip())
        if part and not _is_meta_line(part) and len(part) >= 12:
            candidates.append(part)
    return candidates


def _pick_best_spoken_line(candidates: list[str]) -> str:
    if not candidates:
        return ""

    def score_line(line: str) -> int:
        value = 0
        if "？" in line or line.endswith("?") or "吗" in line:
            value += 3
        if any(token in line for token in ("你", "您", "请", "能否", "可以", "好的")):
            value += 2
        if _is_meta_line(line):
            value -= 10
        return value

    best_score = max(score_line(line) for line in candidates)
    best_lines = [line for line in candidates if score_line(line) == best_score]
    for line in reversed(candidates):
        if line in best_lines:
            return line
    return candidates[-1]


def extract_spoken_response(text: str) -> str:
    content = (text or "").strip()
    if not content or not _looks_like_reasoning_output(content):
        return content

    for marker in _SPOKEN_OUTPUT_MARKERS:
        if marker in content:
            tail = content.rsplit(marker, 1)[-1].strip()
            candidate = _pick_best_spoken_line(_collect_spoken_candidates(tail))
            if candidate:
                return candidate

    candidate = _pick_best_spoken_line(_collect_spoken_candidates(content))
    return candidate or content


def extract_spoken_message(payload: Any) -> str:
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
    content = (text or "").strip()
    if not content:
        raise ValueError("empty response")
    if "```json" in content:
        content = content.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in content:
        content = content.split("```", 1)[1].split("```", 1)[0].strip()

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
