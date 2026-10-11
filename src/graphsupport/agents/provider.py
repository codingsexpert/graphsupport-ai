"""LLM Provider abstraction and client implementations (Phase 5).

Supports Google Gemini and OpenAI-compatible models via resilient HTTP transport
with typed messages, function declarations, tool-calling payloads, timeout guards,
and structured error translation without credential leakage.
"""

import json
import logging
import urllib.parse
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import requests

from graphsupport.config import get_settings
from graphsupport.config.settings import Settings
from graphsupport.core.exceptions import (
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
)

logger = logging.getLogger("graphsupport.agents.provider")


@dataclass
class ToolCall:
    """Structured tool invocation emitted by an LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMMessage:
    """Standardized chat message exchanged with LLM providers."""

    role: str  # 'system', 'user', 'assistant', 'tool'
    content: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass
class ToolDefinition:
    """Schema definition for tools exposed to the LLM."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema format


@dataclass
class ProviderResponse:
    """Typed generation result returned by an LLM provider."""

    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)


class LLMProvider(ABC):
    """Abstract interface defining provider-agnostic text and tool generation."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider service."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model identifier."""
        pass

    @abstractmethod
    def generate(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1500,
    ) -> ProviderResponse:
        """Execute chat completion request with optional tool allowlist."""
        pass


# =============================================================================
# Google Gemini Provider Implementation
# =============================================================================


class GoogleGeminiProvider(LLMProvider):
    """Client for Google Gemini Developer API using generateContent REST endpoint."""

    DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        base_url: str | None = None,
        timeout_sec: float = 30.0,
    ) -> None:
        if not api_key or not api_key.strip():
            raise LLMConfigurationError("Google Gemini API key cannot be empty")
        self._api_key = api_key.strip()
        self._model = (model or "gemini-2.0-flash").strip()
        self._base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._timeout_sec = timeout_sec

    @property
    def provider_name(self) -> str:
        return "google"

    @property
    def model_name(self) -> str:
        return self._model

    def generate(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1500,
    ) -> ProviderResponse:
        """Invoke Gemini generateContent endpoint."""
        url = (
            f"{self._base_url}/models/{self._model}:generateContent"
            f"?key={urllib.parse.quote(self._api_key)}"
        )
        headers = {"Content-Type": "application/json"}

        # 1. Translate messages into Gemini contents & system instruction
        system_instruction: dict[str, Any] | None = None
        contents: list[dict[str, Any]] = []

        for msg in messages:
            if msg.role == "system":
                system_instruction = {"parts": [{"text": msg.content or ""}]}
            elif msg.role == "user":
                contents.append({"role": "user", "parts": [{"text": msg.content or ""}]})
            elif msg.role == "assistant":
                parts: list[dict[str, Any]] = []
                if msg.content:
                    parts.append({"text": msg.content})
                for tc in msg.tool_calls:
                    parts.append(
                        {
                            "functionCall": {
                                "name": tc.name,
                                "args": tc.arguments,
                            }
                        }
                    )
                if not parts:
                    parts.append({"text": ""})
                contents.append({"role": "model", "parts": parts})
            elif msg.role == "tool":
                # Function response part
                tool_data: dict[str, Any]
                try:
                    tool_data = json.loads(msg.content or "{}")
                except Exception:
                    tool_data = {"output": msg.content}
                contents.append(
                    {
                        "role": "function",
                        "parts": [
                            {
                                "functionResponse": {
                                    "name": msg.tool_call_id or "unknown_tool",
                                    "response": tool_data,
                                }
                            }
                        ],
                    }
                )

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction

        # 2. Translate tool declarations
        if tools:
            func_decls = [
                {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                }
                for t in tools
            ]
            payload["tools"] = [{"functionDeclarations": func_decls}]

        # 3. HTTP Execution with error translation
        try:
            resp = requests.post(
                url=url,
                headers=headers,
                json=payload,
                timeout=self._timeout_sec,
            )
        except requests.exceptions.Timeout as err:
            raise LLMTimeoutError(f"Gemini request timed out after {self._timeout_sec}s") from err
        except requests.exceptions.RequestException as err:
            raise LLMError(f"Network error communicating with Gemini provider: {err}") from err

        if resp.status_code == 401 or resp.status_code == 403:
            raise LLMAuthenticationError(
                "Gemini authentication failed: invalid or unauthorized API key"
            )
        if resp.status_code == 429:
            raise LLMRateLimitError(
                "Gemini request rate limit or quota exceeded. Please retry later."
            )
        if resp.status_code >= 400:
            error_msg = f"Gemini API returned HTTP {resp.status_code}"
            try:
                err_json = resp.json()
                if "error" in err_json and "message" in err_json["error"]:
                    error_msg += f": {err_json['error']['message']}"
            except Exception:
                pass
            raise LLMError(error_msg)

        # 4. Parse response
        try:
            resp_json = resp.json()
        except Exception as err:
            raise LLMError("Malformed JSON response returned by Gemini API") from err

        candidates = resp_json.get("candidates", [])
        if not candidates:
            return ProviderResponse(content="", finish_reason="stop")

        candidate = candidates[0]
        c_content = candidate.get("content", {})
        parts = c_content.get("parts", [])

        extracted_text_pieces: list[str] = []
        extracted_tool_calls: list[ToolCall] = []

        for p_idx, part in enumerate(parts):
            if "text" in part:
                extracted_text_pieces.append(part["text"])
            if "functionCall" in part:
                fc = part["functionCall"]
                extracted_tool_calls.append(
                    ToolCall(
                        id=fc.get("name", f"call-{p_idx}"),
                        name=fc.get("name", "unnamed_tool"),
                        arguments=fc.get("args", {}),
                    )
                )

        full_content = "".join(extracted_text_pieces).strip() or None
        usage_meta = resp_json.get("usageMetadata", {})
        usage = {
            "prompt_tokens": usage_meta.get("promptTokenCount", 0),
            "completion_tokens": usage_meta.get("candidatesTokenCount", 0),
            "total_tokens": usage_meta.get("totalTokenCount", 0),
        }

        return ProviderResponse(
            content=full_content,
            tool_calls=extracted_tool_calls,
            finish_reason=candidate.get("finishReason", "STOP"),
            usage=usage,
        )


# =============================================================================
# OpenAI-Compatible Provider Implementation
# =============================================================================


class OpenAIProvider(LLMProvider):
    """Client for OpenAI and OpenAI-compatible API services."""

    DEFAULT_BASE_URL = "https://api.openai.com/v1"

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        base_url: str | None = None,
        timeout_sec: float = 30.0,
    ) -> None:
        if not api_key or not api_key.strip():
            raise LLMConfigurationError("OpenAI API key cannot be empty")
        self._api_key = api_key.strip()
        self._model = (model or "gpt-4o").strip()
        self._base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._timeout_sec = timeout_sec

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model

    def generate(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1500,
    ) -> ProviderResponse:
        """Invoke OpenAI /chat/completions endpoint."""
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

        # Format messages
        formatted_msgs: list[dict[str, Any]] = []
        for msg in messages:
            entry: dict[str, Any] = {"role": msg.role, "content": msg.content or ""}
            if msg.role == "tool" and msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in msg.tool_calls
                ]
            formatted_msgs.append(entry)

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": formatted_msgs,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]
            payload["tool_choice"] = "auto"

        try:
            resp = requests.post(
                url=url,
                headers=headers,
                json=payload,
                timeout=self._timeout_sec,
            )
        except requests.exceptions.Timeout as err:
            raise LLMTimeoutError(f"OpenAI request timed out after {self._timeout_sec}s") from err
        except requests.exceptions.RequestException as err:
            raise LLMError(f"Network error communicating with OpenAI: {err}") from err

        if resp.status_code == 401 or resp.status_code == 403:
            raise LLMAuthenticationError("OpenAI authentication failed: invalid API key")
        if resp.status_code == 429:
            raise LLMRateLimitError("OpenAI rate limit or quota exceeded")
        if resp.status_code >= 400:
            raise LLMError(f"OpenAI returned HTTP {resp.status_code}: {resp.text}")

        try:
            res_data = resp.json()
        except Exception as err:
            raise LLMError("Malformed JSON response from OpenAI API") from err

        choices = res_data.get("choices", [])
        if not choices:
            return ProviderResponse(content="", finish_reason="stop")

        msg = choices[0].get("message", {})
        content = msg.get("content")
        raw_tool_calls = msg.get("tool_calls", [])

        parsed_tcs: list[ToolCall] = []
        for tc in raw_tool_calls:
            f_info = tc.get("function", {})
            args_str = f_info.get("arguments", "{}")
            try:
                args_dict = json.loads(args_str)
            except Exception:
                args_dict = {"raw": args_str}
            parsed_tcs.append(
                ToolCall(
                    id=tc.get("id", "call-0"),
                    name=f_info.get("name", "unknown"),
                    arguments=args_dict,
                )
            )

        usage = res_data.get("usage", {})
        return ProviderResponse(
            content=content,
            tool_calls=parsed_tcs,
            finish_reason=choices[0].get("finish_reason", "stop"),
            usage=usage,
        )


# =============================================================================
# Mock Provider for Unit Tests & Offline Development
# =============================================================================


class MockLLMProvider(LLMProvider):
    """Configurable mock provider enabling deterministic, cost-free testing."""

    def __init__(
        self,
        model: str = "mock-model",
        canned_responses: list[ProviderResponse] | None = None,
    ) -> None:
        self._model = model
        self.call_history: list[dict[str, Any]] = []
        self._responses = list(canned_responses) if canned_responses else []

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return self._model

    def add_response(self, response: ProviderResponse) -> None:
        """Enqueue a canned response to be returned by next generate() call."""
        self._responses.append(response)

    def generate(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1500,
    ) -> ProviderResponse:
        """Record invocation and return next canned response or default echo."""
        self.call_history.append(
            {
                "messages": messages,
                "tools": tools,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        if self._responses:
            return self._responses.pop(0)

        # Default fallback response
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        return ProviderResponse(
            content=f"Mock response to: {last_user}",
            tool_calls=[],
            finish_reason="stop",
        )


# =============================================================================
# Provider Factory
# =============================================================================


def get_llm_provider(
    settings: Settings | None = None,
    override_provider: LLMProvider | None = None,
) -> LLMProvider:
    """Resolve and configure an active LLM provider from settings.

    Args:
        settings: Application settings containing provider name and API key.
        override_provider: Optional injected provider (e.g. MockLLMProvider in tests).

    Returns:
        Configured LLMProvider instance.

    Raises:
        LLMConfigurationError: If provider or API key is not configured.
    """
    if override_provider is not None:
        return override_provider

    active_settings = settings or get_settings()
    if not active_settings.is_llm_configured:
        raise LLMConfigurationError(
            "LLM provider is not configured. Set LLM_PROVIDER and LLM_API_KEY "
            "in your .env file or environment variables."
        )

    provider_type = (active_settings.llm_provider or "").strip().lower()
    api_key = active_settings.llm_api_key.get_secret_value() if active_settings.llm_api_key else ""
    model = active_settings.llm_model or "gemini-2.0-flash"

    if provider_type in ("google", "gemini"):
        return GoogleGeminiProvider(api_key=api_key, model=model)
    elif provider_type == "openai":
        return OpenAIProvider(api_key=api_key, model=model)
    elif provider_type == "mock":
        return MockLLMProvider(model=model)
    else:
        raise LLMConfigurationError(
            f"Unsupported LLM provider '{provider_type}'. Allowed: google, openai, mock"
        )
