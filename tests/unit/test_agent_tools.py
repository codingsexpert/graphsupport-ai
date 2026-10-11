"""Unit tests for Phase 5 ToolRegistry and controlled tool execution.

Validates parameter schemas, customer ownership enforcement, invalid tool handling,
outcome fidelity, and escalation records without direct database operations.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from graphsupport.agents.tool_registry import ToolRegistry
from graphsupport.graph.models import (
    Customer,
    SupportTicket,
    TicketDetails,
    TicketStatus,
    TroubleshootingOutcome,
    TroubleshootingStep,
)


@pytest.fixture
def mock_service() -> MagicMock:
    return MagicMock()


@pytest.fixture
def registry(mock_service: MagicMock) -> ToolRegistry:
    return ToolRegistry(
        support_service=mock_service,
        authorized_customer_id="cust-100",
    )


def test_unregistered_tool_returns_error(registry: ToolRegistry) -> None:
    result = registry.execute_tool("arbitrary_python_exec", {"code": "import os"})
    assert result.success is False
    assert "not an approved tool" in result.error


def test_get_customer_history_enforces_authorized_customer_id(
    registry: ToolRegistry, mock_service: MagicMock
) -> None:
    mock_context = MagicMock()
    mock_context.to_summary_dict.return_value = {"customer_id": "cust-100", "tickets": 2}
    mock_service.retrieve_customer_context.return_value = mock_context

    # Attempt to query another customer's ID in args
    result = registry.execute_tool("get_customer_history", {"customer_id": "cust-OTHER"})

    assert result.success is True
    # Verify service was invoked with the authorized customer ID, not the requested one
    mock_service.retrieve_customer_context.assert_called_once()
    call_kwargs = mock_service.retrieve_customer_context.call_args[1]
    assert call_kwargs["customer_id"] == "cust-100"


def test_get_ticket_status_ownership_violation_raises_error(
    registry: ToolRegistry, mock_service: MagicMock
) -> None:
    # Setup ticket belonging to another customer
    alien_customer = Customer(
        id="cust-ALIEN",
        email="alien@example.com",
        name="Alien User",
        tier="standard",
        created_at=datetime.now(UTC),
    )
    alien_ticket = SupportTicket(
        id="tick-alien",
        customer_id="cust-ALIEN",
        title="Alien Ticket",
        description="Secret ticket",
        status=TicketStatus.OPEN,
        priority="high",
        created_at=datetime.now(UTC),
    )
    mock_service.get_ticket_details.return_value = TicketDetails(
        ticket=alien_ticket,
        customer=alien_customer,
        product=None,
        issue=None,
        troubleshooting_steps=[],
        resolutions=[],
    )

    result = registry.execute_tool("get_ticket_status", {"ticket_id": "tick-alien"})

    assert result.success is False
    assert "Authorization Error" in result.error
    assert "not authorized to access ticket" in result.error


def test_record_troubleshooting_attempt_validates_outcome(
    registry: ToolRegistry, mock_service: MagicMock
) -> None:
    # Setup ticket belonging to authorized customer
    my_customer = Customer(
        id="cust-100",
        email="me@example.com",
        name="My User",
        tier="pro",
        created_at=datetime.now(UTC),
    )
    my_ticket = SupportTicket(
        id="tick-mine",
        customer_id="cust-100",
        title="My Ticket",
        description="My Issue",
        status=TicketStatus.OPEN,
        priority="normal",
        created_at=datetime.now(UTC),
    )
    mock_service.get_ticket_details.return_value = TicketDetails(
        ticket=my_ticket,
        customer=my_customer,
        product=None,
        issue=None,
        troubleshooting_steps=[],
        resolutions=[],
    )

    # 1. Invalid outcome string
    res_bad = registry.execute_tool(
        "record_troubleshooting_attempt",
        {
            "ticket_id": "tick-mine",
            "step_number": 1,
            "action": "Reboot device",
            "outcome": "not_a_real_outcome",
        },
    )
    assert res_bad.success is False
    assert "Validation Error" in res_bad.error

    # 2. Valid failed outcome preserves fidelity
    mock_step = TroubleshootingStep(
        id="step-1",
        ticket_id="tick-mine",
        step_number=1,
        action="Factory Reset",
        outcome=TroubleshootingOutcome.FAILED,
        notes="Device remained in boot loop",
    )
    mock_service.record_troubleshooting_step.return_value = mock_step

    res_good = registry.execute_tool(
        "record_troubleshooting_attempt",
        {
            "ticket_id": "tick-mine",
            "step_number": 1,
            "action": "Factory Reset",
            "outcome": "failed",
            "notes": "Device remained in boot loop",
        },
    )
    assert res_good.success is True
    assert res_good.data["outcome"] == "failed"
    mock_service.record_troubleshooting_step.assert_called_once()


def test_escalate_ticket_records_escalation_workflow(
    registry: ToolRegistry, mock_service: MagicMock
) -> None:
    my_customer = Customer(
        id="cust-100",
        email="me@example.com",
        name="My User",
        tier="pro",
        created_at=datetime.now(UTC),
    )
    my_ticket = SupportTicket(
        id="tick-mine",
        customer_id="cust-100",
        title="My Ticket",
        description="My Issue",
        status=TicketStatus.OPEN,
        priority="normal",
        created_at=datetime.now(UTC),
    )
    mock_service.get_ticket_details.return_value = TicketDetails(
        ticket=my_ticket,
        customer=my_customer,
        product=None,
        issue=None,
        troubleshooting_steps=[],
        resolutions=[],
    )
    mock_step = TroubleshootingStep(
        id="step-99",
        ticket_id="tick-mine",
        step_number=99,
        action="Escalation Request (TIER_2): Hardware failure suspected",
        outcome=TroubleshootingOutcome.PARTIAL,
        notes="Escalated by AI agent",
    )
    mock_service.record_troubleshooting_step.return_value = mock_step

    result = registry.execute_tool(
        "escalate_ticket",
        {
            "ticket_id": "tick-mine",
            "reason": "Hardware failure suspected",
            "target_tier": "tier_2",
        },
    )

    assert result.success is True
    assert result.data["escalated"] is True
    assert result.data["target_tier"] == "tier_2"
    mock_service.update_ticket_status.assert_called_once_with(
        ticket_id="tick-mine",
        new_status=TicketStatus.IN_PROGRESS,
    )
    mock_service.record_troubleshooting_step.assert_called_once()
