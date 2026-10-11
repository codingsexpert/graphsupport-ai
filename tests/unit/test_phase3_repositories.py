"""Unit tests for Phase 3 repositories using mock drivers.

Verifies parameterized Cypher execution, error handling, entity mappings,
and protection against string interpolation.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from graphsupport.core.exceptions import (
    EntityNotFoundError,
    ValidationError,
)
from graphsupport.graph.models import (
    Customer,
    Message,
    Product,
    Resolution,
    SupportTicket,
    TicketStatus,
    TroubleshootingOutcome,
    TroubleshootingStep,
)
from graphsupport.graph.repositories.conversation_repo import ConversationRepository
from graphsupport.graph.repositories.customer_repo import CustomerRepository
from graphsupport.graph.repositories.product_repo import ProductRepository
from graphsupport.graph.repositories.ticket_repo import TicketRepository
from graphsupport.graph.repositories.troubleshooting_repo import TroubleshootingRepository


@pytest.fixture
def mock_driver_manager() -> tuple[MagicMock, MagicMock]:
    """Provide a mock Neo4jDriverManager and mock session."""
    manager = MagicMock()
    session = MagicMock()
    manager.session.return_value.__enter__.return_value = session
    return manager, session


# =============================================================================
# Customer Repository Tests
# =============================================================================


def test_customer_repo_create_customer(mock_driver_manager: tuple[MagicMock, MagicMock]) -> None:
    manager, session = mock_driver_manager
    repo = CustomerRepository(driver_manager=manager, database="testdb")

    mock_record = {
        "id": "cust-test-1",
        "email": "test@example.com",
        "name": "Test User",
        "tier": "pro",
        "created_at": datetime.now(UTC).isoformat(),
        "metadata": "{}",
    }
    session.run.return_value.single.return_value = mock_record

    cust = Customer(
        id="cust-test-1",
        email="test@example.com",
        name="Test User",
        tier="pro",
        created_at=datetime.now(UTC),
    )
    res = repo.create_customer(cust)

    assert res.id == "cust-test-1"
    assert res.email == "test@example.com"
    # Verify query uses parameterized CREATE
    call_args = session.run.call_args[0]
    query, params = call_args[0], call_args[1]
    assert "CREATE (c:Customer" in query
    assert params["id"] == "cust-test-1"
    assert params["email"] == "test@example.com"


def test_customer_repo_list_pagination(mock_driver_manager: tuple[MagicMock, MagicMock]) -> None:
    manager, session = mock_driver_manager
    repo = CustomerRepository(driver_manager=manager, database="testdb")

    with pytest.raises(ValidationError):
        repo.list_customers(limit=0)

    with pytest.raises(ValidationError):
        repo.list_customers(limit=50, skip=-1)

    session.run.return_value = []
    customers = repo.list_customers(limit=10, skip=5)
    assert customers == []
    query, params = session.run.call_args[0]
    assert params["limit"] == 10
    assert params["skip"] == 5


# =============================================================================
# Product Repository Tests
# =============================================================================


def test_product_repo_upsert_and_get(mock_driver_manager: tuple[MagicMock, MagicMock]) -> None:
    manager, session = mock_driver_manager
    repo = ProductRepository(driver_manager=manager, database="testdb")

    mock_record = {
        "id": "prod-1",
        "name": "Cloud DB",
        "sku": "CDB-01",
        "category": "database",
        "version": "1.0",
        "metadata": "{}",
    }
    session.run.return_value.single.return_value = mock_record

    prod = Product(id="prod-1", name="Cloud DB", sku="CDB-01")
    saved = repo.upsert_product(prod)
    assert saved.id == "prod-1"
    assert saved.sku == "CDB-01"

    found = repo.get_by_id("prod-1")
    assert found is not None
    assert found.name == "Cloud DB"


def test_product_repo_link_customer(mock_driver_manager: tuple[MagicMock, MagicMock]) -> None:
    manager, session = mock_driver_manager
    repo = ProductRepository(driver_manager=manager, database="testdb")

    session.run.return_value.single.return_value = {"linked": 1}
    success = repo.link_customer_to_product("cust-1", "prod-1")
    assert success is True

    call_args = session.run.call_args[0]
    query, params = call_args[0], call_args[1]
    assert "MERGE (c)-[r:USES]->(p)" in query
    assert params["customer_id"] == "cust-1"
    assert params["product_id"] == "prod-1"


def test_product_repo_link_missing_entities(
    mock_driver_manager: tuple[MagicMock, MagicMock],
) -> None:
    manager, session = mock_driver_manager
    repo = ProductRepository(driver_manager=manager, database="testdb")

    # Linked count 0, then customer existence check returns False
    session.run.return_value.single.side_effect = [{"linked": 0}, {"ex": False}]
    with pytest.raises(EntityNotFoundError) as exc:
        repo.link_customer_to_product("cust-missing", "prod-1")
    assert "Customer with ID 'cust-missing' does not exist" in str(exc.value)


# =============================================================================
# Ticket & Issue Repository Tests
# =============================================================================


def test_ticket_repo_create_ticket_with_issue(
    mock_driver_manager: tuple[MagicMock, MagicMock],
) -> None:
    manager, session = mock_driver_manager
    repo = TicketRepository(driver_manager=manager, database="testdb")

    mock_record = {
        "id": "tkt-1",
        "title": "System slow",
        "description": "High latency in queries",
        "status": "open",
        "priority": "high",
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": None,
        "customer_id": "cust-1",
        "product_id": "prod-1",
        "issue_id": "iss-1",
    }
    session.run.return_value.single.return_value = mock_record

    tkt = SupportTicket(
        id="tkt-1",
        title="System slow",
        description="High latency in queries",
        status=TicketStatus.OPEN,
        priority="high",
        customer_id="cust-1",
        product_id="prod-1",
        issue_id="iss-1",
    )
    created = repo.create_ticket(
        ticket=tkt,
        customer_id="cust-1",
        product_id="prod-1",
        issue_id="iss-1",
    )
    assert created.id == "tkt-1"
    assert created.status == TicketStatus.OPEN
    assert created.customer_id == "cust-1"

    query = session.run.call_args[0][0]
    assert "MERGE (c)-[:HAS_TICKET]->(t)" in query
    assert "MERGE (t)-[:AFFECTS]->(p)" in query
    assert "MERGE (i)-[:TRACKED_BY]->(t)" in query


def test_ticket_repo_update_status(mock_driver_manager: tuple[MagicMock, MagicMock]) -> None:
    manager, session = mock_driver_manager
    repo = TicketRepository(driver_manager=manager, database="testdb")

    updated_record = {
        "id": "tkt-1",
        "title": "Title",
        "description": "Desc",
        "status": "resolved",
        "priority": "medium",
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
        "customer_id": "cust-1",
        "product_id": "prod-1",
        "issue_id": None,
    }

    session.run.return_value.single.return_value = updated_record
    updated = repo.update_ticket_status("tkt-1", TicketStatus.RESOLVED)
    assert updated.status == TicketStatus.RESOLVED


# =============================================================================
# Conversation Repository Tests
# =============================================================================


def test_conversation_repo_append_message(mock_driver_manager: tuple[MagicMock, MagicMock]) -> None:
    manager, session = mock_driver_manager
    repo = ConversationRepository(driver_manager=manager, database="testdb")

    mock_msg_record = {
        "id": "msg-1",
        "sender_type": "customer",
        "content": "Can you check my ticket?",
        "sequence_number": 1,
        "timestamp": datetime.now(UTC).isoformat(),
        "conversation_id": "conv-1",
        "ticket_id": "tkt-1",
    }
    session.run.return_value.single.return_value = mock_msg_record

    msg = Message(
        id="msg-1",
        sender_type="customer",
        content="Can you check my ticket?",
        sequence_number=1,
        conversation_id="conv-1",
        ticket_id="tkt-1",
    )
    persisted = repo.append_message(msg, conversation_id="conv-1", ticket_id="tkt-1")

    assert persisted.id == "msg-1"
    assert persisted.sequence_number == 1
    query, params = session.run.call_args[0]
    assert "MERGE (conv)-[:CONTAINS]->(m)" in query
    assert "MERGE (m)-[:ABOUT]->(t)" in query
    assert params["content"] == "Can you check my ticket?"


def test_conversation_messages_ordering(mock_driver_manager: tuple[MagicMock, MagicMock]) -> None:
    manager, session = mock_driver_manager
    repo = ConversationRepository(driver_manager=manager, database="testdb")

    session.run.return_value = []
    repo.get_conversation_messages("conv-1")
    query, params = session.run.call_args[0]
    assert "ORDER BY m.sequence_number ASC, m.timestamp ASC, m.id ASC" in query
    assert params["conversation_id"] == "conv-1"


# =============================================================================
# Troubleshooting Repository Tests
# =============================================================================


def test_troubleshooting_repo_record_step_and_resolution(
    mock_driver_manager: tuple[MagicMock, MagicMock],
) -> None:
    manager, session = mock_driver_manager
    repo = TroubleshootingRepository(driver_manager=manager, database="testdb")

    # 1. Step test
    # Simulate ticket existence check (ex: True), then record return
    session.run.return_value.single.side_effect = [
        {"ex": True},  # ticket check
        {
            "id": "step-1",
            "step_number": 1,
            "action": "Cleared cache",
            "outcome": "success",
            "notes": "Cache cleared in 200ms",
            "executed_at": datetime.now(UTC).isoformat(),
            "ticket_id": "tkt-1",
            "previous_step_id": None,
        },
    ]

    step = TroubleshootingStep(
        id="step-1",
        step_number=1,
        action="Cleared cache",
        outcome=TroubleshootingOutcome.SUCCESS,
        ticket_id="tkt-1",
    )
    saved_step = repo.record_step(step, ticket_id="tkt-1")
    assert saved_step.outcome == TroubleshootingOutcome.SUCCESS

    # 2. Resolution test
    session.run.return_value.single.side_effect = [
        {"ex": True},  # ticket check
        {
            "id": "res-1",
            "summary": "Resolved by flushing cache",
            "resolution_type": "fix",
            "verified": True,
            "created_at": datetime.now(UTC).isoformat(),
            "ticket_id": "tkt-1",
        },
    ]

    res = Resolution(
        id="res-1",
        summary="Resolved by flushing cache",
        resolution_type="fix",
        ticket_id="tkt-1",
    )
    saved_res = repo.record_resolution(res, ticket_id="tkt-1")
    assert saved_res.verified is True
    assert saved_res.id == "res-1"
