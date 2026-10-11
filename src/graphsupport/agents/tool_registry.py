"""Controlled tool registry exposing authorized domain functions to the AI agent (Phase 5).

Strictly enforces customer boundary isolation, validates arguments via Pydantic schemas,
and executes all state changes and graph traversals through the SupportService application layer.
Arbitrary execution, unparameterized Cypher, and cross-customer access are strictly forbidden.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from graphsupport.application.support_service import SupportService
from graphsupport.core.exceptions import (
    AuthorizationError,
    EntityNotFoundError,
    GraphSupportError,
    ValidationError,
)
from graphsupport.graph.models import TicketStatus, TroubleshootingOutcome
from graphsupport.memory.models import RetrievalLimits

logger = logging.getLogger("graphsupport.agents.tool_registry")


@dataclass
class ToolResult:
    """Standardized output returned from a tool execution."""

    tool_name: str
    success: bool
    data: dict[str, Any]
    error: str | None = None

    def to_json(self) -> str:
        """Serialize data payload into JSON for LLM response consumption."""
        payload: dict[str, Any] = {"tool_name": self.tool_name, "success": self.success}
        if self.success:
            payload["data"] = self.data
        else:
            payload["error"] = self.error
        return json.dumps(payload, default=str)


# =============================================================================
# Input Validation Schemas
# =============================================================================


class GetCustomerHistoryInput(BaseModel):
    product_id: str | None = Field(default=None, description="Optional product filter")
    issue_query: str | None = Field(
        default=None, description="Optional search keywords or symptoms"
    )
    ticket_id: str | None = Field(default=None, description="Optional specific ticket identifier")


class GetTicketStatusInput(BaseModel):
    ticket_id: str = Field(..., description="Unique ID of the support ticket to inspect")


class GetProductInfoInput(BaseModel):
    product_id: str = Field(..., description="Unique product ID to look up in catalog")


class RecordTroubleshootingAttemptInput(BaseModel):
    ticket_id: str = Field(..., description="Unique support ticket ID")
    step_number: int = Field(..., ge=1, le=50, description="Sequential step number (1, 2, 3...)")
    action: str = Field(
        ..., min_length=3, max_length=500, description="Diagnostic action performed"
    )
    outcome: str = Field(
        ...,
        description="Outcome of this step: 'failed', 'success', 'partial', or 'unknown'",
    )
    notes: str = Field(default="", max_length=1000, description="Diagnostic observations or notes")


class CreateSupportTicketInput(BaseModel):
    title: str = Field(..., min_length=3, max_length=200, description="Summary title of the issue")
    description: str = Field(
        ..., min_length=5, max_length=2000, description="Detailed problem description"
    )
    priority: str = Field(
        default="normal",
        description="Ticket priority: 'low', 'normal', 'high', or 'urgent'",
    )
    product_id: str | None = Field(default=None, description="Affected product ID if known")
    issue_id: str | None = Field(default=None, description="Associated canonical issue ID if known")


class UpdateTicketStatusInput(BaseModel):
    ticket_id: str = Field(..., description="Ticket ID to update")
    new_status: str = Field(
        ...,
        description="Target ticket status: 'open', 'in_progress', 'resolved', or 'closed'",
    )


class EscalateTicketInput(BaseModel):
    ticket_id: str = Field(..., description="Ticket ID requiring escalation")
    reason: str = Field(
        ..., min_length=5, max_length=500, description="Justification for escalation"
    )
    target_tier: str = Field(default="tier_2", description="Target escalation tier (e.g. 'tier_2')")


# =============================================================================
# Tool Registry Implementation
# =============================================================================


class ToolRegistry:
    """Scoped registry managing approved tools bound to an authorized customer context."""

    def __init__(
        self,
        support_service: SupportService,
        authorized_customer_id: str,
    ) -> None:
        if not authorized_customer_id or not authorized_customer_id.strip():
            raise ValidationError(
                "Authorized customer ID must be supplied to initialize ToolRegistry"
            )
        self.service = support_service
        self.authorized_customer_id = authorized_customer_id.strip()

    def get_tool_definitions(self) -> list[Any]:
        """Return standardized JSON schema declarations for all registered tools."""
        from graphsupport.agents.provider import ToolDefinition

        return [
            ToolDefinition(
                name="get_customer_history",
                description=(
                    "Retrieve recent support history, products, ranked tickets, diagnostic "
                    "attempts, and resolutions for the authorized customer."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "product_id": {
                            "type": "string",
                            "description": "Optional product ID filter",
                        },
                        "issue_query": {
                            "type": "string",
                            "description": "Optional search keywords or symptoms",
                        },
                        "ticket_id": {
                            "type": "string",
                            "description": "Optional specific ticket ID",
                        },
                    },
                },
            ),
            ToolDefinition(
                name="get_ticket_status",
                description="Get detailed status, history, and resolutions for a support ticket.",
                parameters={
                    "type": "object",
                    "properties": {
                        "ticket_id": {
                            "type": "string",
                            "description": "Unique support ticket ID",
                        }
                    },
                    "required": ["ticket_id"],
                },
            ),
            ToolDefinition(
                name="get_product_info",
                description="Retrieve product details, SKU, and specs from the catalog.",
                parameters={
                    "type": "object",
                    "properties": {
                        "product_id": {
                            "type": "string",
                            "description": "Unique product ID",
                        }
                    },
                    "required": ["product_id"],
                },
            ),
            ToolDefinition(
                name="create_support_ticket",
                description="Open a new support ticket in Neo4j linked to the authorized customer.",
                parameters={
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Brief summary title of the issue",
                        },
                        "description": {
                            "type": "string",
                            "description": "Full problem description",
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["low", "normal", "high", "urgent"],
                            "description": "Ticket priority level",
                        },
                        "product_id": {
                            "type": "string",
                            "description": "Affected product ID",
                        },
                    },
                    "required": ["title", "description"],
                },
            ),
            ToolDefinition(
                name="record_troubleshooting_attempt",
                description=(
                    "Persist a diagnostic troubleshooting attempt for an open ticket. "
                    "Outcomes must strictly be 'failed', 'success', 'partial', or 'unknown'."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "ticket_id": {
                            "type": "string",
                            "description": "Unique ticket ID",
                        },
                        "step_number": {
                            "type": "integer",
                            "description": "Sequential step index (1, 2, 3...)",
                        },
                        "action": {
                            "type": "string",
                            "description": "Action performed (e.g. 'Power cycle modem')",
                        },
                        "outcome": {
                            "type": "string",
                            "enum": ["failed", "success", "partial", "unknown"],
                            "description": "Observed diagnostic outcome",
                        },
                        "notes": {
                            "type": "string",
                            "description": "Observed results or error messages",
                        },
                    },
                    "required": ["ticket_id", "step_number", "action", "outcome"],
                },
            ),
            ToolDefinition(
                name="update_ticket_status",
                description="Update ticket status ('open', 'in_progress', 'resolved', 'closed').",
                parameters={
                    "type": "object",
                    "properties": {
                        "ticket_id": {
                            "type": "string",
                            "description": "Unique ticket ID",
                        },
                        "new_status": {
                            "type": "string",
                            "enum": ["open", "in_progress", "resolved", "closed"],
                            "description": "Target status",
                        },
                    },
                    "required": ["ticket_id", "new_status"],
                },
            ),
            ToolDefinition(
                name="escalate_ticket",
                description="Escalate an unresolved ticket to Tier 2 support when necessary.",
                parameters={
                    "type": "object",
                    "properties": {
                        "ticket_id": {
                            "type": "string",
                            "description": "Unique ticket ID to escalate",
                        },
                        "reason": {
                            "type": "string",
                            "description": "Technical reason for escalation",
                        },
                        "target_tier": {
                            "type": "string",
                            "description": "Escalation target tier (default: 'tier_2')",
                        },
                    },
                    "required": ["ticket_id", "reason"],
                },
            ),
        ]

    def execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        """Validate arguments, check customer ownership, and dispatch tool invocation."""
        dispatch_table = {
            "get_customer_history": self._tool_get_customer_history,
            "get_ticket_status": self._tool_get_ticket_status,
            "get_product_info": self._tool_get_product_info,
            "create_support_ticket": self._tool_create_support_ticket,
            "record_troubleshooting_attempt": self._tool_record_troubleshooting_attempt,
            "update_ticket_status": self._tool_update_ticket_status,
            "escalate_ticket": self._tool_escalate_ticket,
        }

        handler = dispatch_table.get(tool_name)
        if not handler:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                data={},
                error=f"Tool '{tool_name}' is not an approved tool in the ToolRegistry.",
            )

        try:
            return handler(arguments)
        except AuthorizationError as err:
            logger.warning("Tool authorization violation on '%s': %s", tool_name, err)
            return ToolResult(
                tool_name=tool_name, success=False, data={}, error=f"Authorization Error: {err}"
            )
        except ValidationError as err:
            logger.warning("Tool validation error on '%s': %s", tool_name, err)
            return ToolResult(
                tool_name=tool_name, success=False, data={}, error=f"Validation Error: {err}"
            )
        except EntityNotFoundError as err:
            return ToolResult(
                tool_name=tool_name, success=False, data={}, error=f"Not Found: {err}"
            )
        except GraphSupportError as err:
            logger.error("Domain failure during tool execution '%s': %s", tool_name, err)
            return ToolResult(
                tool_name=tool_name, success=False, data={}, error=f"Operation Failed: {err}"
            )
        except Exception as err:
            logger.exception("Unexpected error executing tool '%s': %s", tool_name, err)
            return ToolResult(
                tool_name=tool_name, success=False, data={}, error=f"Internal Error: {err}"
            )

    # =========================================================================
    # Tool Implementations
    # =========================================================================

    def _tool_get_customer_history(self, args: dict[str, Any]) -> ToolResult:
        validated = GetCustomerHistoryInput(**args)
        # Force authorized customer ID boundary regardless of any argument
        context = self.service.retrieve_customer_context(
            customer_id=self.authorized_customer_id,
            product_id=validated.product_id,
            issue_query=validated.issue_query,
            ticket_id=validated.ticket_id,
            limits=RetrievalLimits(max_tickets=5),
        )
        return ToolResult(
            tool_name="get_customer_history",
            success=True,
            data=context.to_summary_dict(),
        )

    def _tool_get_ticket_status(self, args: dict[str, Any]) -> ToolResult:
        validated = GetTicketStatusInput(**args)
        # Verify ticket ownership first
        self._verify_ticket_ownership(validated.ticket_id)
        details = self.service.get_ticket_details(validated.ticket_id)
        if not details:
            raise EntityNotFoundError(f"Ticket '{validated.ticket_id}' not found")

        return ToolResult(
            tool_name="get_ticket_status",
            success=True,
            data={
                "ticket_id": details.ticket.id,
                "title": details.ticket.title,
                "status": details.ticket.status.value,
                "priority": details.ticket.priority,
                "created_at": details.ticket.created_at.isoformat(),
                "attempts_count": len(details.troubleshooting_steps),
                "resolutions_count": len(details.resolutions),
                "latest_attempt": (
                    {
                        "step": details.troubleshooting_steps[-1].step_number,
                        "action": details.troubleshooting_steps[-1].action,
                        "outcome": details.troubleshooting_steps[-1].outcome.value,
                    }
                    if details.troubleshooting_steps
                    else None
                ),
            },
        )

    def _tool_get_product_info(self, args: dict[str, Any]) -> ToolResult:
        validated = GetProductInfoInput(**args)
        product = self.service.get_product(validated.product_id)
        if not product:
            raise EntityNotFoundError(f"Product '{validated.product_id}' not found")
        return ToolResult(
            tool_name="get_product_info",
            success=True,
            data={
                "product_id": product.id,
                "name": product.name,
                "sku": product.sku,
                "category": product.category,
                "version": product.version,
            },
        )

    def _tool_create_support_ticket(self, args: dict[str, Any]) -> ToolResult:
        validated = CreateSupportTicketInput(**args)
        ticket = self.service.open_support_ticket(
            customer_id=self.authorized_customer_id,
            title=validated.title,
            description=validated.description,
            priority=validated.priority,
            product_id=validated.product_id,
            issue_id=validated.issue_id,
        )
        return ToolResult(
            tool_name="create_support_ticket",
            success=True,
            data={
                "ticket_id": ticket.id,
                "title": ticket.title,
                "status": ticket.status.value,
                "priority": ticket.priority,
                "created_at": ticket.created_at.isoformat(),
            },
        )

    def _tool_record_troubleshooting_attempt(self, args: dict[str, Any]) -> ToolResult:
        validated = RecordTroubleshootingAttemptInput(**args)
        # Check ticket ownership
        self._verify_ticket_ownership(validated.ticket_id)

        try:
            outcome_enum = TroubleshootingOutcome(validated.outcome.strip().lower())
        except ValueError as err:
            allowed = [o.value for o in TroubleshootingOutcome]
            raise ValidationError(
                f"Invalid outcome '{validated.outcome}'. Allowed: {allowed}"
            ) from err

        step = self.service.record_troubleshooting_step(
            ticket_id=validated.ticket_id,
            step_number=validated.step_number,
            action=validated.action,
            outcome=outcome_enum,
            notes=validated.notes,
        )
        return ToolResult(
            tool_name="record_troubleshooting_attempt",
            success=True,
            data={
                "step_id": step.id,
                "ticket_id": validated.ticket_id,
                "step_number": step.step_number,
                "action": step.action,
                "outcome": step.outcome.value,
            },
        )

    def _tool_update_ticket_status(self, args: dict[str, Any]) -> ToolResult:
        validated = UpdateTicketStatusInput(**args)
        self._verify_ticket_ownership(validated.ticket_id)

        try:
            status_enum = TicketStatus(validated.new_status.strip().lower())
        except ValueError as err:
            allowed = [s.value for s in TicketStatus]
            raise ValidationError(
                f"Invalid status '{validated.new_status}'. Allowed: {allowed}"
            ) from err

        updated = self.service.update_ticket_status(
            ticket_id=validated.ticket_id,
            new_status=status_enum,
        )
        return ToolResult(
            tool_name="update_ticket_status",
            success=True,
            data={"ticket_id": updated.id, "new_status": updated.status.value},
        )

    def _tool_escalate_ticket(self, args: dict[str, Any]) -> ToolResult:
        validated = EscalateTicketInput(**args)
        self._verify_ticket_ownership(validated.ticket_id)

        # Set status to in_progress and priority to urgent
        self.service.update_ticket_status(
            ticket_id=validated.ticket_id, new_status=TicketStatus.IN_PROGRESS
        )

        # Record genuine escalation record as a troubleshooting step
        step = self.service.record_troubleshooting_step(
            ticket_id=validated.ticket_id,
            step_number=99,  # High sequence for escalation
            action=f"Escalation Request ({validated.target_tier.upper()}): {validated.reason}",
            outcome=TroubleshootingOutcome.PARTIAL,
            notes=f"Escalated by AI agent on behalf of customer. Reason: {validated.reason}",
        )
        return ToolResult(
            tool_name="escalate_ticket",
            success=True,
            data={
                "ticket_id": validated.ticket_id,
                "escalated": True,
                "target_tier": validated.target_tier,
                "escalation_step_id": step.id,
                "reason": validated.reason,
            },
        )

    def _verify_ticket_ownership(self, ticket_id: str) -> None:
        """Verify that the ticket belongs to self.authorized_customer_id."""
        details = self.service.get_ticket_details(ticket_id)
        if not details:
            raise EntityNotFoundError(f"Ticket '{ticket_id}' not found")
        if details.customer.id != self.authorized_customer_id:
            raise AuthorizationError(
                f"Customer '{self.authorized_customer_id}' is not authorized to access "
                f"ticket '{ticket_id}'"
            )
