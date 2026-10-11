"""Domain and Graph entity models for GraphSupport AI.

Defines typed Pydantic models for graph nodes, relationships, composite views, and status enums.
Uses application-level generated identifiers (UUID4) for stable identity across sessions.
"""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TicketStatus(StrEnum):
    """Lifecycle status of a support ticket."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TroubleshootingOutcome(StrEnum):
    """Outcome of a diagnostic or troubleshooting attempt."""

    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


def _generate_id() -> str:
    """Generate a durable random UUID4 hex string."""
    return uuid.uuid4().hex


def _utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(UTC)


class BaseGraphModel(BaseModel):
    """Base model for all graph entities."""

    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )


class Customer(BaseGraphModel):
    """Customer entity node (:Customer)."""

    id: str = Field(default_factory=_generate_id, description="Stable UUID identifier")
    email: str = Field(
        ..., min_length=3, max_length=254, description="Customer unique email address"
    )
    name: str = Field(..., min_length=1, max_length=150, description="Customer full name")
    tier: str = Field(default="standard", description="Account tier: standard, pro, enterprise")
    created_at: datetime = Field(default_factory=_utc_now, description="Account creation timestamp")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary customer metadata"
    )

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        """Basic email validation check."""
        clean = v.strip().lower()
        if "@" not in clean or "." not in clean:
            raise ValueError(f"Invalid email format: '{v}'")
        return clean

    @field_validator("name")
    @classmethod
    def validate_name_not_blank(cls, v: str) -> str:
        """Ensure name contains printable characters."""
        clean = v.strip()
        if not clean:
            raise ValueError("Customer name cannot be empty or whitespace only")
        return clean


class Product(BaseGraphModel):
    """Product catalog entity node (:Product)."""

    id: str = Field(default_factory=_generate_id, description="Stable UUID identifier")
    name: str = Field(..., min_length=1, max_length=150, description="Product display name")
    sku: str = Field(..., min_length=1, max_length=64, description="Unique product SKU code")
    category: str = Field(default="general", description="Product category or hardware family")
    version: str = Field(default="1.0.0", description="Product or firmware version")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Product specifications")

    @field_validator("name", "sku")
    @classmethod
    def validate_non_blank(cls, v: str) -> str:
        """Validate non-empty strings."""
        clean = v.strip()
        if not clean:
            raise ValueError("Product fields cannot be blank")
        return clean


class Issue(BaseGraphModel):
    """Known symptom or defect entity node (:Issue)."""

    id: str = Field(default_factory=_generate_id, description="Stable UUID identifier")
    title: str = Field(
        ..., min_length=1, max_length=200, description="Short canonical title of issue"
    )
    description: str = Field(
        default="", max_length=2000, description="Technical problem description"
    )
    category: str = Field(default="general", description="Issue category (hardware, network, etc.)")
    severity: str = Field(default="medium", description="Severity: low, medium, high, critical")
    product_id: str | None = Field(default=None, description="Optional parent product ID")
    created_at: datetime = Field(default_factory=_utc_now, description="Identification timestamp")


class SupportTicket(BaseGraphModel):
    """Customer support ticket entity node (:SupportTicket)."""

    id: str = Field(default_factory=_generate_id, description="Stable UUID identifier")
    title: str = Field(..., min_length=1, max_length=200, description="Ticket subject line")
    description: str = Field(
        default="", max_length=4000, description="Detailed customer issue report"
    )
    status: TicketStatus = Field(default=TicketStatus.OPEN, description="Current workflow state")
    priority: str = Field(default="normal", description="Priority level: low, normal, urgent")
    customer_id: str | None = Field(default=None, description="Linked customer identifier")
    product_id: str | None = Field(default=None, description="Linked product identifier")
    issue_id: str | None = Field(default=None, description="Linked issue identifier")
    created_at: datetime = Field(default_factory=_utc_now, description="Ticket opening timestamp")
    updated_at: datetime | None = Field(default=None, description="Last status update timestamp")


class Conversation(BaseGraphModel):
    """Customer support session node (:Conversation)."""

    id: str = Field(default_factory=_generate_id, description="Stable UUID identifier")
    customer_id: str | None = Field(default=None, description="Owner customer identifier")
    session_id: str = Field(default_factory=_generate_id, description="Chat session key")
    channel: str = Field(default="web", description="Interaction channel: web, email, api")
    started_at: datetime = Field(default_factory=_utc_now, description="Conversation start time")
    status: str = Field(default="active", description="Conversation state: active, archived")


class Message(BaseGraphModel):
    """Transcript entry node (:Message)."""

    id: str = Field(default_factory=_generate_id, description="Stable UUID identifier")
    conversation_id: str | None = Field(default=None, description="Parent conversation ID")
    sender_type: str = Field(..., description="Sender role: customer, agent, or system")
    content: str = Field(..., min_length=1, max_length=8000, description="Message text content")
    sequence_number: int = Field(default=1, ge=1, description="Deterministic sequence order")
    ticket_id: str | None = Field(default=None, description="Optional referenced ticket ID")
    timestamp: datetime = Field(default_factory=_utc_now, description="Dispatch timestamp")

    @field_validator("sender_type")
    @classmethod
    def validate_sender(cls, v: str) -> str:
        """Validate sender type is recognized."""
        allowed = {"customer", "agent", "assistant", "system", "user"}
        clean = v.strip().lower()
        if clean not in allowed:
            raise ValueError(f"Invalid sender_type '{v}'. Allowed: {allowed}")
        return clean


class TroubleshootingStep(BaseGraphModel):
    """Ordered troubleshooting step node (:TroubleshootingStep)."""

    id: str = Field(default_factory=_generate_id, description="Stable UUID identifier")
    ticket_id: str | None = Field(default=None, description="Parent ticket ID")
    step_number: int = Field(default=1, ge=1, description="Sequence index in workflow")
    action: str = Field(
        ..., min_length=1, max_length=1000, description="Diagnostic action performed"
    )
    outcome: TroubleshootingOutcome = Field(
        default=TroubleshootingOutcome.UNKNOWN,
        description="Outcome of the diagnostic step",
    )
    notes: str | None = Field(
        default=None, max_length=2000, description="Observations or error outputs"
    )
    executed_at: datetime = Field(default_factory=_utc_now, description="Execution timestamp")
    previous_step_id: str | None = Field(
        default=None, description="Preceding step ID in [:FOLLOWED_BY] chain"
    )


class Resolution(BaseGraphModel):
    """Verified resolution node (:Resolution)."""

    id: str = Field(default_factory=_generate_id, description="Stable UUID identifier")
    ticket_id: str | None = Field(default=None, description="Parent ticket ID")
    summary: str = Field(
        ..., min_length=1, max_length=2000, description="Explanation of fix/workaround"
    )
    resolution_type: str = Field(
        default="workaround",
        description="Type: fix, workaround, replacement, configuration",
    )
    verified: bool = Field(default=True, description="Whether customer confirmed resolution")
    created_at: datetime = Field(default_factory=_utc_now, description="Resolution record time")


class TicketDetails(BaseGraphModel):
    """Comprehensive ticket context with related nodes and resolution history."""

    ticket: SupportTicket
    customer: Customer | None = None
    product: Product | None = None
    issue: Issue | None = None
    troubleshooting_steps: list[TroubleshootingStep] = Field(default_factory=list)
    resolutions: list[Resolution] = Field(default_factory=list)


class ConversationDetails(BaseGraphModel):
    """Conversation context containing ordered messages."""

    conversation: Conversation
    messages: list[Message] = Field(default_factory=list)
