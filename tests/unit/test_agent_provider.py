"""Unit tests for Phase 5 LLM Provider abstraction and client error mapping.

Validates Google Gemini and OpenAI message formatting, function declarations,
timeout handling, authentication failure mapping, and mock provider mechanics
without making live network or paid API calls.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from graphsupport.agents.provider import (
    GoogleGeminiProvider,
    LLMMessage,
    MockLLMProvider,
    OpenAIProvider,
    ProviderResponse,
    ToolCall,
    ToolDefinition,
    get_llm_provider,
)
from graphsupport.config.settings import Settings
from graphsupport.core.exceptions import (
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMRateLimitError,
    LLMTimeoutError,
)


def test_get_llm_provider_unconfigured_raises_error() -> None:
    settings = Settings(llm_provider=None, llm_api_key=None)
    with pytest.raises(LLMConfigurationError, match="LLM provider is not configured"):
        get_llm_provider(settings)


def test_get_llm_provider_mock_resolution() -> None:
    settings = Settings(llm_provider="mock", llm_api_key="dummy-key", llm_model="mock-v1")
    provider = get_llm_provider(settings)
    assert isinstance(provider, MockLLMProvider)
    assert provider.model_name == "mock-v1"


def test_mock_provider_returns_enqueued_responses() -> None:
    provider = MockLLMProvider()
    canned = ProviderResponse(
        content="I can help with that router.",
        tool_calls=[ToolCall(id="call-1", name="get_product_info", arguments={"product_id": "p1"})],
        finish_reason="stop",
    )
    provider.add_response(canned)

    resp = provider.generate([LLMMessage(role="user", content="Hello")])
    assert resp.content == "I can help with that router."
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "get_product_info"


@patch("requests.post")
def test_gemini_provider_success_translation(mock_post: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "Your gateway was rebooted recently."},
                        {
                            "functionCall": {
                                "name": "get_ticket_status",
                                "args": {"ticket_id": "tick-123"},
                            }
                        },
                    ]
                },
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 50,
            "candidatesTokenCount": 20,
            "totalTokenCount": 70,
        },
    }
    mock_post.return_value = mock_resp

    provider = GoogleGeminiProvider(api_key="test-gemini-key", model="gemini-2.0-flash")
    messages = [
        LLMMessage(role="system", content="System rules"),
        LLMMessage(role="user", content="Check my ticket"),
    ]
    tools = [
        ToolDefinition(
            name="get_ticket_status",
            description="Check ticket status",
            parameters={"type": "object", "properties": {"ticket_id": {"type": "string"}}},
        )
    ]

    response = provider.generate(messages, tools=tools)

    assert response.content == "Your gateway was rebooted recently."
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].name == "get_ticket_status"
    assert response.tool_calls[0].arguments == {"ticket_id": "tick-123"}
    assert response.usage["total_tokens"] == 70

    # Verify request payload structure
    call_args = mock_post.call_args
    sent_payload = call_args[1]["json"]
    assert "contents" in sent_payload
    assert "systemInstruction" in sent_payload
    assert "tools" in sent_payload


@patch("requests.post")
def test_gemini_provider_auth_error(mock_post: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.json.return_value = {"error": {"message": "API key not valid"}}
    mock_post.return_value = mock_resp

    provider = GoogleGeminiProvider(api_key="bad-key")
    with pytest.raises(LLMAuthenticationError, match="authentication failed"):
        provider.generate([LLMMessage(role="user", content="Hi")])


@patch("requests.post")
def test_gemini_provider_rate_limit(mock_post: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_post.return_value = mock_resp

    provider = GoogleGeminiProvider(api_key="test-key")
    with pytest.raises(LLMRateLimitError, match="rate limit or quota exceeded"):
        provider.generate([LLMMessage(role="user", content="Hi")])


@patch("requests.post")
def test_gemini_provider_timeout(mock_post: MagicMock) -> None:
    mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")

    provider = GoogleGeminiProvider(api_key="test-key", timeout_sec=2.0)
    with pytest.raises(LLMTimeoutError, match="timed out"):
        provider.generate([LLMMessage(role="user", content="Hi")])


@patch("requests.post")
def test_openai_provider_success(mock_post: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "Hello from OpenAI",
                    "tool_calls": [
                        {
                            "id": "call-abc",
                            "function": {
                                "name": "get_product_info",
                                "arguments": '{"product_id": "prod-1"}',
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"total_tokens": 42},
    }
    mock_post.return_value = mock_resp

    provider = OpenAIProvider(api_key="sk-test", model="gpt-4o")
    res = provider.generate([LLMMessage(role="user", content="Hello")])

    assert res.content == "Hello from OpenAI"
    assert len(res.tool_calls) == 1
    assert res.tool_calls[0].name == "get_product_info"
    assert res.tool_calls[0].arguments == {"product_id": "prod-1"}
