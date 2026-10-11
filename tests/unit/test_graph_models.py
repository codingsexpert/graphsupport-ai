"""Unit tests for GraphSupport AI graph entity domain models and enums."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from graphsupport.graph.models import (
    Conversation,
    Customer,
    Message,
    Product,
    Resolution,
    SupportTicket,
    TicketStatus,
    TroubleshootingOutcome,
    TroubleshootingStep,
)


def test_customer_model_defaults() -> None:
    """Verify Customer model default ID generation and timestamp."""
    customer = Customer(email="alice@example.com", name="Alice Wonderland")

    assert customer.id is not None
    assert len(customer.id) == 32  # UUID4 hex
    assert customer.email == "alice@example.com"
    assert customer.name == "Alice Wonderland"
    assert customer.tier == "standard"
    assert isinstance(customer.created_at, datetime)
    assert customer.metadata == {}


def test_product_model() -> None:
    """Verify Product catalog model properties."""
    product = Product(name="Enterprise Router X1", sku="RT-X1-PRO", category="networking")

    assert product.id is not None
    assert product.name == "Enterprise Router X1"
    assert product.sku == "RT-X1-PRO"
    assert product.version == "1.0.0"


def test_ticket_status_enum() -> None:
    """Verify TicketStatus enum values."""
    assert TicketStatus.OPEN == "open"
    assert TicketStatus.IN_PROGRESS == "in_progress"
    assert TicketStatus.RESOLVED == "resolved"
    assert TicketStatus.CLOSED == "closed"


def test_troubleshooting_outcome_enum() -> None:
    """Verify TroubleshootingOutcome enum values."""
    assert TroubleshootingOutcome.SUCCESS == "success"
    assert TroubleshootingOutcome.FAILED == "failed"
    assert TroubleshootingOutcome.PARTIAL == "partial"
    assert TroubleshootingOutcome.UNKNOWN == "unknown"


def test_support_ticket_model() -> None:
    """Verify SupportTicket status and priority defaults."""
    ticket = SupportTicket(title="Connection dropping frequently")

    assert ticket.id is not None
    assert ticket.status == TicketStatus.OPEN
    assert ticket.priority == "normal"
    assert ticket.updated_at is None


def test_invalid_ticket_status_raises_validation_error() -> None:
    """Verify that assigning an invalid status raises ValidationError."""
    with pytest.raises(ValidationError):
        SupportTicket(title="Faulty", status="invalid_status")  # type: ignore[arg-type]


def test_troubleshooting_step_model() -> None:
    """Verify TroubleshootingStep model."""
    step = TroubleshootingStep(
        step_number=1,
        action="Reboot modem and verify link light",
        outcome=TroubleshootingOutcome.SUCCESS,
        notes="Link came back after 30 seconds",
    )

    assert step.step_number == 1
    assert step.outcome == TroubleshootingOutcome.SUCCESS
    assert step.notes == "Link came back after 30 seconds"


def test_resolution_model() -> None:
    """Verify Resolution model."""
    res = Resolution(
        summary="Replaced faulty cable and upgraded router firmware to 1.0.4",
        resolution_type="fix",
        verified=True,
    )

    assert res.id is not None
    assert res.verified is True
    assert res.resolution_type == "fix"


def test_conversation_and_message_models() -> None:
    """Verify Conversation and Message models."""
    conv = Conversation(session_id="session-123", channel="web")
    msg = Message(sender_type="customer", content="Help, my wifi is down!")

    assert conv.channel == "web"
    assert conv.status == "active"
    assert msg.sender_type == "customer"
    assert msg.content == "Help, my wifi is down!"
    assert msg.timestamp.tzinfo is not None or msg.timestamp.year >= 2026
