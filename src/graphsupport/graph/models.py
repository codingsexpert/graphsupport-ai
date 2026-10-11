"""Domain and Graph entity models for GraphSupport AI.

Defines typed Pydantic models for graph nodes, relationships, and status enums.
Uses application-level generated identifiers (UUID4) for stable identity across sessions.
"""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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
    email: str = Field(..., description="Customer unique email address")
    name: str = Field(..., description="Customer full name")
    tier: str = Field(default="standard", description="Account tier: standard, pro, enterprise")
    created_at: datetime = Field(default_factory=_utc_now, description="Account creation timestamp")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary customer metadata"
    )


class Product(BaseGraphModel):
    """Product catalog entity node (:Product)."""

    id: str = Field(default_factory=_generate_id, description="Stable UUID identifier")
    name: str = Field(..., description="Product display name")
    sku: str = Field(..., description="Unique product SKU code")
    category: str = Field(default="general", description="Product category or hardware family")
    version: str = Field(default="1.0.0", description="Product or firmware version")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Product specifications")


class Issue(BaseGraphModel):
    """Known symptom or defect entity node (:Issue)."""

    id: str = Field(default_factory=_generate_id, description="Stable UUID identifier")
    title: str = Field(..., description="Short canonical title of issue")
    description: str = Field(default="", description="Technical problem description")
    category: str = Field(default="general", description="Issue category (hardware, network, etc.)")
    severity: str = Field(default="medium", description="Severity: low, medium, high, critical")
    created_at: datetime = Field(default_factory=_utc_now, description="Identification timestamp")


class SupportTicket(BaseGraphModel):
    """Customer support ticket entity node (:SupportTicket)."""

    id: str = Field(default_factory=_generate_id, description="Stable UUID identifier")
    title: str = Field(..., description="Ticket subject line")
    description: str = Field(default="", description="Detailed issue report from customer")
    status: TicketStatus = Field(default=TicketStatus.OPEN, description="Current workflow state")
    priority: str = Field(default="normal", description="Priority level: low, normal, urgent")
    created_at: datetime = Field(default_factory=_utc_now, description="Ticket opening timestamp")
    updated_at: datetime | None = Field(default=None, description="Last status update timestamp")


class Conversation(BaseGraphModel):
    """Customer support session node (:Conversation)."""

    id: str = Field(default_factory=_generate_id, description="Stable UUID identifier")
    session_id: str = Field(default_factory=_generate_id, description="Chat session key")
    channel: str = Field(default="web", description="Interaction channel: web, email, api")
    started_at: datetime = Field(default_factory=_utc_now, description="Conversation start time")
    status: str = Field(default="active", description="Conversation state: active, archived")


class Message(BaseGraphModel):
    """Transcript entry node (:Message)."""

    id: str = Field(default_factory=_generate_id, description="Stable UUID identifier")
    sender_type: str = Field(..., description="Sender role: customer, agent, or system")
    content: str = Field(..., description="Message text content")
    timestamp: datetime = Field(default_factory=_utc_now, description="Dispatch timestamp")


class TroubleshootingStep(BaseGraphModel):
    """Ordered troubleshooting step node (:TroubleshootingStep)."""

    id: str = Field(default_factory=_generate_id, description="Stable UUID identifier")
    step_number: int = Field(default=1, description="Sequence index in workflow")
    action: str = Field(..., description="Diagnostic action performed or recommended")
    outcome: TroubleshootingOutcome = Field(
        default=TroubleshootingOutcome.UNKNOWN,
        description="Outcome of the diagnostic step",
    )
    notes: str | None = Field(default=None, description="Observations or error outputs")
    executed_at: datetime = Field(default_factory=_utc_now, description="Execution timestamp")


class Resolution(BaseGraphModel):
    """Verified resolution node (:Resolution)."""

    id: str = Field(default_factory=_generate_id, description="Stable UUID identifier")
    summary: str = Field(..., description="Clear explanation of the fix or workaround")
    resolution_type: str = Field(
        default="workaround",
        description="Type: fix, workaround, replacement, configuration",
    )
    verified: bool = Field(default=True, description="Whether customer confirmed resolution")
    created_at: datetime = Field(default_factory=_utc_now, description="Resolution record time")
