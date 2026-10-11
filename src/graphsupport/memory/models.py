"""Typed domain models for GraphSupport AI persistent graph memory (Phase 4).

Defines structured memory contexts, ranked ticket containers, retrieval limits,
and transparency metadata for deterministic LLM context assembly.
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from graphsupport.graph.models import (
    ConversationDetails,
    Customer,
    Issue,
    Message,
    Product,
    Resolution,
    SupportTicket,
    TroubleshootingStep,
)


def _utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(UTC)


class RetrievalLimits(BaseModel):
    """Configurable boundaries for memory extraction and context assembly."""

    model_config = ConfigDict(frozen=True)

    max_tickets: int = Field(default=5, ge=1, le=50, description="Max ranked tickets")
    max_attempts_per_ticket: int = Field(
        default=5, ge=1, le=20, description="Max diagnostic attempts per ticket"
    )
    max_conversations: int = Field(default=3, ge=1, le=10, description="Max recent conversations")
    max_messages_per_conversation: int = Field(
        default=10, ge=1, le=50, description="Max messages per conversation"
    )
    max_resolutions_per_ticket: int = Field(
        default=3, ge=1, le=10, description="Max resolutions per ticket"
    )


class RankedTicketContext(BaseModel):
    """Enriched support ticket with graph linkages, diagnostic history, and scoring rationale."""

    model_config = ConfigDict(frozen=True)

    ticket: SupportTicket
    relevance_score: float = Field(ge=0.0, description="Deterministic ranking score")
    ranking_reasons: list[str] = Field(
        default_factory=list, description="Explainable scoring breakdown"
    )
    product: Product | None = Field(default=None, description="Affected product node")
    issue: Issue | None = Field(default=None, description="Tracked canonical issue node")
    troubleshooting_attempts: list[TroubleshootingStep] = Field(
        default_factory=list, description="Sequential diagnostic attempts"
    )
    resolutions: list[Resolution] = Field(
        default_factory=list, description="Verified or recorded resolutions"
    )
    related_messages: list[Message] = Field(
        default_factory=list, description="Messages explicitly referencing this ticket"
    )


class MemoryRetrievalMetadata(BaseModel):
    """Audit and diagnostic metadata explaining how memory context was assembled."""

    model_config = ConfigDict(frozen=True)

    queried_customer_id: str
    queried_product_id: str | None = None
    queried_ticket_id: str | None = None
    issue_query: str | None = None
    retrieved_at: datetime = Field(default_factory=_utc_now)
    total_tickets_found: int = 0
    tickets_included: int = 0
    total_attempts_found: int = 0
    total_conversations_found: int = 0


class CustomerMemoryContext(BaseModel):
    """Complete structured graph memory context for a customer.

    Designed for deterministic inspection and bounded prompt assembly
    in the Phase 5 LLM reasoning layer.
    """

    model_config = ConfigDict(frozen=True)

    customer: Customer
    products: list[Product] = Field(
        default_factory=list, description="Products associated with customer"
    )
    ranked_tickets: list[RankedTicketContext] = Field(
        default_factory=list, description="Ranked support tickets with context"
    )
    recent_conversations: list[ConversationDetails] = Field(
        default_factory=list, description="Recent conversation sessions and messages"
    )
    retrieval_metadata: MemoryRetrievalMetadata
    missing_information: list[str] = Field(
        default_factory=list, description="Explicit indicators of missing or unverified facts"
    )

    def to_summary_dict(self) -> dict[str, Any]:
        """Convert memory context into a clean, serializable summary."""
        return {
            "customer_id": self.customer.id,
            "customer_name": self.customer.name,
            "tier": self.customer.tier,
            "product_count": len(self.products),
            "ranked_tickets_count": len(self.ranked_tickets),
            "missing_information": self.missing_information,
            "retrieved_at": self.retrieval_metadata.retrieved_at.isoformat(),
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert complete memory context into a JSON-serializable dictionary."""
        return self.model_dump(mode="json")
