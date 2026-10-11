"""Core AI Support Agent orchestrator for GraphSupport AI (Phase 5).

Coordinates grounded customer conversations:
1. Validates incoming message and customer identity boundary.
2. Retrieves persistent customer graph memory from Neo4j.
3. Assembles prompt with system instructions and graph evidence.
4. Executes controlled tools with customer ownership enforcement.
5. Limits tool loops and validates final response against grounded facts.
6. Persists conversation transcripts safely in Neo4j.
"""

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from graphsupport.agents.output_parser import OutputParser
from graphsupport.agents.prompt_templates import assemble_agent_messages
from graphsupport.agents.provider import (
    LLMMessage,
    LLMProvider,
    ProviderResponse,
    get_llm_provider,
)
from graphsupport.agents.tool_registry import ToolRegistry, ToolResult
from graphsupport.application.support_service import SupportService
from graphsupport.core.exceptions import (
    LLMError,
    ValidationError,
)
from graphsupport.core.rate_limiter import get_rate_limiter
from graphsupport.core.security import (
    sanitize_text_input,
    scan_for_prompt_injection,
    validate_entity_id,
)
from graphsupport.memory.models import CustomerMemoryContext, RetrievalLimits

logger = logging.getLogger("graphsupport.agents.support_agent")


@dataclass
class ToolExecutionRecord:
    """Audit record of a tool invocation during an agent turn."""

    tool_name: str
    arguments: dict[str, Any]
    success: bool
    data: dict[str, Any]
    error: str | None = None
    duration_ms: float = 0.0
    correlation_id: str | None = None


@dataclass
class AgentResponse:
    """Typed result returned to the UI or client following an agent turn."""

    response_text: str
    conversation_id: str
    tool_executions: list[ToolExecutionRecord] = field(default_factory=list)
    memory_context_used: CustomerMemoryContext | None = None
    iterations_used: int = 1
    claims_verified: bool = True
    correlation_id: str = ""
    injection_flagged: bool = False


class SupportAgent:
    """Context-aware AI support agent backed by Neo4j graph memory and controlled tools."""

    def __init__(
        self,
        support_service: SupportService,
        llm_provider: LLMProvider | None = None,
        max_tool_iterations: int = 4,
        max_history_tickets: int = 5,
        output_parser: OutputParser | None = None,
    ) -> None:
        self.service = support_service
        self.provider = llm_provider or get_llm_provider()
        self.max_tool_iterations = max_tool_iterations
        self.max_history_tickets = max_history_tickets
        self.output_parser = output_parser or OutputParser()

    def handle_message(
        self,
        customer_id: str,
        message: str,
        conversation_id: str | None = None,
        focused_ticket_id: str | None = None,
        focused_product_id: str | None = None,
    ) -> AgentResponse:
        """Execute a grounded support agent turn.

        Args:
            customer_id: Verified customer ID for the active identity boundary.
            message: User inquiry text.
            conversation_id: Optional existing conversation session ID.
            focused_ticket_id: Optional ticket ID to prioritize in memory retrieval.
            focused_product_id: Optional product ID to filter in memory retrieval.

        Returns:
            AgentResponse containing verified assistant text, conversation ID, and audit trail.

        Raises:
            ValidationError: If customer or message inputs are invalid.
            RateLimitExceededError: If customer request rate threshold is exceeded.
            EntityNotFoundError: If customer does not exist in graph.
            AuthorizationError: If ticket does not belong to customer.
            LLMError: If provider fails or credentials are unconfigured.
        """
        # 1. Input Validation and Correlation Tracking
        req_id = f"req-{uuid.uuid4().hex[:10]}"
        cid = validate_entity_id(customer_id, "Customer ID")
        clean_msg = sanitize_text_input(message, max_chars=3000, field_name="Customer message")
        if not clean_msg:
            raise ValidationError("Customer message cannot be empty")

        tid = (
            validate_entity_id(focused_ticket_id, "Focused ticket ID")
            if focused_ticket_id
            else None
        )
        pid = (
            validate_entity_id(focused_product_id, "Focused product ID")
            if focused_product_id
            else None
        )

        # 2. Rate Limiting Enforcement
        get_rate_limiter().enforce_rate_limit(cid)

        # 3. Prompt Injection Heuristic Scan
        is_injection_flagged, injection_reason = scan_for_prompt_injection(clean_msg)
        if is_injection_flagged:
            logger.warning(
                "[%s] Security scan flagged potential prompt injection for customer=%s: %s",
                req_id,
                cid,
                injection_reason,
            )

        logger.info(
            "[%s] Agent request for customer=%s (conv=%s, ticket=%s, product=%s)",
            req_id,
            cid,
            conversation_id,
            tid,
            pid,
        )

        # 4. Resolve or create active conversation
        conv_id = conversation_id.strip() if conversation_id else None
        if not conv_id:
            conv = self.service.start_conversation(
                customer_id=cid,
                channel="ai_chat",
                conversation_id=f"conv-{uuid.uuid4().hex[:12]}",
            )
            conv_id = conv.id

        # 5. Persist incoming customer message first
        self.service.add_message(
            conversation_id=conv_id,
            sender_type="customer",
            content=clean_msg,
            ticket_id=tid,
            authorized_customer_id=cid,
        )

        # 6. Retrieve persistent customer graph memory
        limits = RetrievalLimits(max_tickets=self.max_history_tickets)
        memory_context = self.service.retrieve_customer_context(
            customer_id=cid,
            product_id=pid,
            ticket_id=tid,
            issue_query=clean_msg,
            limits=limits,
        )

        # 7. Initialize customer-scoped tool registry
        tool_registry = ToolRegistry(
            support_service=self.service,
            authorized_customer_id=cid,
        )
        tool_defs = tool_registry.get_tool_definitions()

        # 8. Assemble prompt messages
        messages = assemble_agent_messages(
            context=memory_context,
            user_message=clean_msg,
        )

        # 9. Agent reasoning and tool loop
        tool_executions: list[ToolExecutionRecord] = []
        iteration = 0
        final_text: str | None = None

        while iteration < self.max_tool_iterations:
            iteration += 1

            # Call provider
            try:
                resp: ProviderResponse = self.provider.generate(
                    messages=messages,
                    tools=tool_defs,
                )
            except LLMError:
                # Re-raise typed LLM errors for application-level handling
                raise
            except Exception as err:
                raise LLMError(f"Unexpected error communicating with LLM provider: {err}") from err

            # Check if model requested tool execution
            if resp.tool_calls:
                # Append assistant message with requested tool calls
                messages.append(
                    LLMMessage(
                        role="assistant",
                        content=resp.content,
                        tool_calls=resp.tool_calls,
                    )
                )

                for tc in resp.tool_calls:
                    logger.info(
                        "[%s] Executing agent tool: %s with args: %s",
                        req_id,
                        tc.name,
                        tc.arguments,
                    )
                    result: ToolResult = tool_registry.execute_tool(
                        tool_name=tc.name,
                        arguments=tc.arguments,
                        correlation_id=req_id,
                    )

                    record = ToolExecutionRecord(
                        tool_name=tc.name,
                        arguments=tc.arguments,
                        success=result.success,
                        data=result.data,
                        error=result.error,
                        duration_ms=result.duration_ms,
                        correlation_id=req_id,
                    )
                    tool_executions.append(record)

                    # Feed tool response back to the conversation
                    messages.append(
                        LLMMessage(
                            role="tool",
                            content=result.to_json(),
                            tool_call_id=tc.name,
                        )
                    )
                # Next loop iteration allows model to reason over tool outputs
                continue

            # Model produced a terminal response
            final_text = resp.content
            break

        # Fallback if loop exhausted without terminal response
        if final_text is None:
            logger.warning(
                "[%s] Agent reached maximum tool iterations (%d) for customer %s",
                req_id,
                self.max_tool_iterations,
                cid,
            )
            final_text = (
                "I've initiated the requested actions on your account, but reached the maximum "
                "processing limit for this turn. Your records have been updated in the database."
            )

        # 10. Output Validation & Sanitization
        raw_tool_dicts = [
            {"tool_name": r.tool_name, "args": r.arguments, "success": r.success}
            for r in tool_executions
        ]
        val_result = self.output_parser.parse_and_validate(
            raw_text=final_text,
            context=memory_context,
            executed_tool_records=raw_tool_dicts,
        )

        # 11. Persist final assistant response to conversation
        self.service.add_message(
            conversation_id=conv_id,
            sender_type="assistant",
            content=val_result.sanitized_text,
            ticket_id=tid,
            authorized_customer_id=cid,
        )

        return AgentResponse(
            response_text=val_result.sanitized_text,
            conversation_id=conv_id,
            tool_executions=tool_executions,
            memory_context_used=memory_context,
            iterations_used=iteration,
            claims_verified=val_result.claims_verified,
            correlation_id=req_id,
            injection_flagged=is_injection_flagged,
        )
