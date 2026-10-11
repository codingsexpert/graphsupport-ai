"""Agents module for GraphSupport AI (Phase 5).

Provides context-aware AI support agent, LLM provider abstraction, controlled
tool execution, trusted system prompt templates, and factual output validation.
"""

from graphsupport.agents.output_parser import OutputParser, ValidationResult
from graphsupport.agents.prompt_templates import (
    BASE_SYSTEM_INSTRUCTIONS,
    assemble_agent_messages,
    format_memory_context_for_prompt,
)
from graphsupport.agents.provider import (
    GoogleGeminiProvider,
    LLMMessage,
    LLMProvider,
    MockLLMProvider,
    OpenAIProvider,
    ProviderResponse,
    ToolCall,
    ToolDefinition,
    get_llm_provider,
)
from graphsupport.agents.support_agent import (
    AgentResponse,
    SupportAgent,
    ToolExecutionRecord,
)
from graphsupport.agents.tool_registry import ToolRegistry, ToolResult

__all__ = [
    "SupportAgent",
    "AgentResponse",
    "ToolExecutionRecord",
    "LLMProvider",
    "GoogleGeminiProvider",
    "OpenAIProvider",
    "MockLLMProvider",
    "get_llm_provider",
    "ToolCall",
    "LLMMessage",
    "ProviderResponse",
    "ToolDefinition",
    "ToolRegistry",
    "ToolResult",
    "OutputParser",
    "ValidationResult",
    "assemble_agent_messages",
    "format_memory_context_for_prompt",
    "BASE_SYSTEM_INSTRUCTIONS",
]
