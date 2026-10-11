"""Unit tests for Sarvam AI LLM provider integration.

Verifies:
1. Provider initialization, defaults, and API key validation.
2. Dual header authentication (api-subscription-key & Bearer).
3. OpenAI-compatible request payload serialization (messages, tools, temperatures).
4. Response parsing (plain text and structured tool calls).
5. Structured error translation (401 -> LLMAuthenticationError, 429 -> LLMRateLimitError, timeouts).
6. Factory instantiation through get_llm_provider().
"""

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from graphsupport.agents.provider import (
    LLMMessage,
    SarvamAIProvider,
    ToolCall,
    ToolDefinition,
    get_llm_provider,
)
from graphsupport.config.settings import Settings
from graphsupport.core.exceptions import (
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
)


def test_sarvam_provider_init_validation() -> None:
    """Verify provider validates API key and sets default model and base URL."""
    with pytest.raises(LLMConfigurationError, match="Sarvam AI API key cannot be empty"):
        SarvamAIProvider(api_key="")

    with pytest.raises(LLMConfigurationError, match="Sarvam AI API key cannot be empty"):
        SarvamAIProvider(api_key="   ")

    provider = SarvamAIProvider(api_key="sarvam-test-key")
    assert provider.provider_name == "sarvam"
    assert provider.model_name == "sarvam-105b"
    assert provider._base_url == "https://api.sarvam.ai/v1"


def test_sarvam_provider_custom_model_and_url() -> None:
    """Verify provider respects custom model identifier and base URL."""
    provider = SarvamAIProvider(
        api_key="sarvam-test-key",
        model="sarvam-2b",
        base_url="https://api.sarvam.ai/v1/",
        timeout_sec=15.0,
    )
    assert provider.model_name == "sarvam-2b"
    assert provider._base_url == "https://api.sarvam.ai/v1"
    assert provider._timeout_sec == 15.0


@patch("requests.post")
def test_sarvam_provider_generate_text_success(mock_post: MagicMock) -> None:
    """Verify successful chat completion parses assistant text and usage."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Namaste! How may I assist you with your SmartMesh Gateway?",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 40, "completion_tokens": 15, "total_tokens": 55},
    }
    mock_post.return_value = mock_resp

    provider = SarvamAIProvider(api_key="test-key-123", model="sarvam-105b")
    messages = [
        LLMMessage(role="system", content="You are a helpful support agent."),
        LLMMessage(role="user", content="Hello, I need help with login."),
    ]

    response = provider.generate(messages=messages, temperature=0.3, max_tokens=500)

    assert response.content == "Namaste! How may I assist you with your SmartMesh Gateway?"
    assert response.finish_reason == "stop"
    assert response.tool_calls == []
    assert response.usage.get("total_tokens") == 55

    # Check request headers and body
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args[1]
    headers = call_kwargs["headers"]
    assert headers["api-subscription-key"] == "test-key-123"
    assert headers["Authorization"] == "Bearer test-key-123"
    assert headers["Content-Type"] == "application/json"

    payload = call_kwargs["json"]
    assert payload["model"] == "sarvam-105b"
    assert len(payload["messages"]) == 2
    assert payload["temperature"] == 0.3
    assert payload["max_tokens"] == 500


@patch("requests.post")
def test_sarvam_provider_generate_tool_calls(mock_post: MagicMock) -> None:
    """Verify tool call responses are parsed into typed ToolCall instances."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call-sarvam-1",
                            "type": "function",
                            "function": {
                                "name": "get_ticket_status",
                                "arguments": json.dumps({"ticket_id": "demo-tkt-101"}),
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"total_tokens": 80},
    }
    mock_post.return_value = mock_resp

    provider = SarvamAIProvider(api_key="test-key-123")
    tools = [
        ToolDefinition(
            name="get_ticket_status",
            description="Lookup status of a ticket",
            parameters={
                "type": "object",
                "properties": {"ticket_id": {"type": "string"}},
                "required": ["ticket_id"],
            },
        )
    ]
    messages = [LLMMessage(role="user", content="Check status for ticket 101")]

    response = provider.generate(messages=messages, tools=tools)

    assert len(response.tool_calls) == 1
    tc = response.tool_calls[0]
    assert isinstance(tc, ToolCall)
    assert tc.name == "get_ticket_status"
    assert tc.arguments == {"ticket_id": "demo-tkt-101"}
    assert response.finish_reason == "tool_calls"


@patch("requests.post")
def test_sarvam_provider_authentication_error(mock_post: MagicMock) -> None:
    """Verify HTTP 401 translates to LLMAuthenticationError."""
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = "Unauthorized: Invalid subscription key"
    mock_post.return_value = mock_resp

    provider = SarvamAIProvider(api_key="bad-key")
    with pytest.raises(LLMAuthenticationError, match="invalid api-subscription-key"):
        provider.generate(messages=[LLMMessage(role="user", content="Hello")])


@patch("requests.post")
def test_sarvam_provider_rate_limit_error(mock_post: MagicMock) -> None:
    """Verify HTTP 429 translates to LLMRateLimitError."""
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.text = "Too Many Requests"
    mock_post.return_value = mock_resp

    provider = SarvamAIProvider(api_key="valid-key")
    with pytest.raises(LLMRateLimitError, match="rate limit or quota exceeded"):
        provider.generate(messages=[LLMMessage(role="user", content="Hello")])


@patch("requests.post")
def test_sarvam_provider_timeout_error(mock_post: MagicMock) -> None:
    """Verify network timeout translates to LLMTimeoutError."""
    mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")

    provider = SarvamAIProvider(api_key="valid-key", timeout_sec=5.0)
    with pytest.raises(LLMTimeoutError, match="timed out after 5.0s"):
        provider.generate(messages=[LLMMessage(role="user", content="Hello")])


@patch("requests.post")
def test_sarvam_provider_server_error(mock_post: MagicMock) -> None:
    """Verify HTTP 500 translates to general LLMError."""
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"
    mock_post.return_value = mock_resp

    provider = SarvamAIProvider(api_key="valid-key")
    with pytest.raises(LLMError, match="HTTP 500"):
        provider.generate(messages=[LLMMessage(role="user", content="Hello")])


def test_get_llm_provider_factory_resolves_sarvam() -> None:
    """Verify factory initializes SarvamAIProvider when configured in settings."""
    settings = Settings(
        _env_file=None,
        llm_provider="sarvam",
        sarvam_api_key="sarvam-secret-key-999",
        sarvam_model="sarvam-2b",
    )
    provider = get_llm_provider(settings=settings)
    assert isinstance(provider, SarvamAIProvider)
    assert provider.provider_name == "sarvam"
    assert provider.model_name == "sarvam-2b"
