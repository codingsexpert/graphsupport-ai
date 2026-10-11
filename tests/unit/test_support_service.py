"""Unit tests for SupportService application layer.

Tests validation rules, entity orchestration, authorization boundary guards,
and error conversions using mock repositories.
"""

from unittest.mock import MagicMock

import pytest

from graphsupport.application.support_service import SupportService
from graphsupport.core.exceptions import (
    AuthorizationError,
    EntityNotFoundError,
    ValidationError,
)
from graphsupport.graph.models import (
    Conversation,
    Customer,
    Message,
    Product,
    SupportTicket,
    TicketStatus,
)


@pytest.fixture
def mock_service() -> tuple[SupportService, dict[str, MagicMock]]:
    """Create a SupportService with mocked repositories."""
    repos = {
        "customer": MagicMock(),
        "product": MagicMock(),
        "ticket": MagicMock(),
        "conversation": MagicMock(),
        "troubleshooting": MagicMock(),
    }
    service = SupportService(
        customer_repo=repos["customer"],
        product_repo=repos["product"],
        ticket_repo=repos["ticket"],
        conversation_repo=repos["conversation"],
        troubleshooting_repo=repos["troubleshooting"],
    )
    return service, repos


# =============================================================================
# Customer Operations Tests
# =============================================================================


def test_register_customer_validation(
    mock_service: tuple[SupportService, dict[str, MagicMock]],
) -> None:
    service, repos = mock_service

    # Invalid email
    with pytest.raises(ValidationError) as exc:
        service.register_customer(email="invalid-email", name="Test User")
    assert "Invalid email format" in str(exc.value)

    # Empty name
    with pytest.raises(ValidationError) as exc:
        service.register_customer(email="user@test.com", name="   ")
    assert "Customer name must be between" in str(exc.value)

    # Invalid tier
    with pytest.raises(ValidationError) as exc:
        service.register_customer(email="user@test.com", name="Test", tier="super-vip")
    assert "Invalid customer tier" in str(exc.value)

    # Successful call
    repos["customer"].create_customer.return_value = Customer(
        id="cust-1", email="user@test.com", name="Test", tier="standard"
    )
    c = service.register_customer(email="user@test.com", name="Test")
    assert c.id == "cust-1"
    repos["customer"].create_customer.assert_called_once()


def test_update_customer_validation(
    mock_service: tuple[SupportService, dict[str, MagicMock]],
) -> None:
    service, repos = mock_service

    with pytest.raises(ValidationError):
        service.update_customer_profile(customer_id="   ", name="Valid")

    with pytest.raises(ValidationError):
        service.update_customer_profile(customer_id="c-1", tier="unknown-tier")


# =============================================================================
# Product Operations Tests
# =============================================================================


def test_product_service_validation(
    mock_service: tuple[SupportService, dict[str, MagicMock]],
) -> None:
    service, repos = mock_service

    # Empty SKU
    with pytest.raises(ValidationError) as exc:
        service.register_or_update_product(name="Widget", sku="   ")
    assert "Product SKU must be between" in str(exc.value)

    # Link with empty customer ID
    with pytest.raises(ValidationError):
        service.associate_customer_with_product(customer_id="", product_id="prod-1")

    # Successful upsert
    repos["product"].upsert_product.return_value = Product(
        id="prod-sku1", name="Widget", sku="SKU1"
    )
    p = service.register_or_update_product(name="Widget", sku="sku1")
    assert p.sku == "SKU1"


# =============================================================================
# Ticket & Issue Operations Tests
# =============================================================================


def test_ticket_service_validation(
    mock_service: tuple[SupportService, dict[str, MagicMock]],
) -> None:
    service, repos = mock_service

    # Issue validation
    with pytest.raises(ValidationError):
        service.record_issue(product_id="p-1", title="", description="Desc")

    with pytest.raises(ValidationError):
        service.record_issue(
            product_id="p-1", title="Title", description="Desc", severity="extreme"
        )

    # Ticket priority validation
    with pytest.raises(ValidationError):
        service.open_support_ticket(
            customer_id="c-1",
            product_id="p-1",
            title="Title",
            description="Desc",
            priority="asap",
        )

    # Status transition validation
    with pytest.raises(ValidationError):
        service.transition_ticket_status(ticket_id="t-1", new_status="abandoned")

    repos["ticket"].update_ticket_status.return_value = SupportTicket(
        id="t-1",
        title="T",
        description="D",
        status=TicketStatus.CLOSED,
        priority="low",
    )
    t = service.transition_ticket_status("t-1", TicketStatus.CLOSED)
    assert t.status == TicketStatus.CLOSED


# =============================================================================
# Conversation & Message Authorization Tests
# =============================================================================


def test_conversation_authorization_boundary(
    mock_service: tuple[SupportService, dict[str, MagicMock]],
) -> None:
    service, repos = mock_service

    # Customer missing when starting conversation
    repos["customer"].get_by_id.return_value = None
    with pytest.raises(EntityNotFoundError):
        service.start_conversation(customer_id="non-existent")

    # Conversation belongs to cust-owner
    conv = Conversation(
        id="conv-1",
        session_id="sess-1",
        channel="chat",
        status="active",
        customer_id="cust-owner",
    )
    repos["conversation"].get_by_id.return_value = conv

    # Unauthorized access: cust-intruder tries to append a message
    with pytest.raises(AuthorizationError) as exc:
        service.add_message(
            conversation_id="conv-1",
            sender_type="customer",
            content="Hello",
            authorized_customer_id="cust-intruder",
        )
    assert "is not authorized" in str(exc.value)

    # Authorized access: cust-owner appends message
    repos["conversation"].get_conversation_messages.return_value = []
    repos["conversation"].append_message.return_value = Message(
        id="msg-1",
        sender_type="customer",
        content="Hello",
        sequence_number=1,
        conversation_id="conv-1",
    )
    msg = service.add_message(
        conversation_id="conv-1",
        sender_type="customer",
        content="Hello",
        authorized_customer_id="cust-owner",
    )
    assert msg.id == "msg-1"
    assert msg.sequence_number == 1


def test_message_validation(mock_service: tuple[SupportService, dict[str, MagicMock]]) -> None:
    service, repos = mock_service

    # Invalid sender type
    with pytest.raises(ValidationError):
        service.add_message(
            conversation_id="conv-1",
            sender_type="hacker",
            content="Hello",
        )

    # Content length exceeding 4000
    with pytest.raises(ValidationError):
        service.add_message(
            conversation_id="conv-1",
            sender_type="customer",
            content="x" * 4001,
        )


# =============================================================================
# Troubleshooting & Resolution Operations Tests
# =============================================================================


def test_troubleshooting_service_validation(
    mock_service: tuple[SupportService, dict[str, MagicMock]],
) -> None:
    service, repos = mock_service

    with pytest.raises(ValidationError):
        service.record_troubleshooting_step(
            ticket_id="t-1",
            step_number=0,  # Must be >= 1
            action="Action",
            outcome="success",
        )

    with pytest.raises(ValidationError):
        service.record_troubleshooting_step(
            ticket_id="t-1",
            step_number=1,
            action="Action",
            outcome="unknown_outcome",  # Invalid enum
        )

    with pytest.raises(ValidationError):
        service.record_ticket_resolution(ticket_id="t-1", summary="")
