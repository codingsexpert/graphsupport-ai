"""Unit tests for CustomerRepository graph operations."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from neo4j.exceptions import Neo4jError

from graphsupport.core.exceptions import RepositoryError
from graphsupport.graph.models import Customer
from graphsupport.graph.repository import CustomerRepository


def _mock_customer_record(
    customer_id: str = "cust-1",
    email: str = "cust1@example.com",
    name: str = "John Doe",
    tier: str = "standard",
) -> dict:
    return {
        "id": customer_id,
        "email": email,
        "name": name,
        "tier": tier,
        "created_at": datetime.now(UTC).isoformat(),
        "metadata": '{"plan": "basic"}',
    }


def test_upsert_customer_success() -> None:
    """Verify upsert_customer executes parameterized Cypher MERGE and returns entity."""
    mock_manager = MagicMock()
    mock_session = MagicMock()
    mock_manager.session.return_value.__enter__.return_value = mock_session

    mock_result = MagicMock()
    mock_result.single.return_value = _mock_customer_record(
        customer_id="cust-123", email="john@example.com", name="John"
    )
    mock_session.run.return_value = mock_result

    repo = CustomerRepository(driver_manager=mock_manager, database="testdb")
    customer = Customer(id="cust-123", email="john@example.com", name="John")

    persisted = repo.upsert_customer(customer)

    assert persisted.id == "cust-123"
    assert persisted.email == "john@example.com"
    assert persisted.name == "John"

    # Verify query was parameterized (run called with query and params dict)
    call_args = mock_session.run.call_args
    query, params = call_args[0]
    assert "MERGE (c:Customer {id: $id})" in query
    assert params["id"] == "cust-123"
    assert params["email"] == "john@example.com"
    assert "john@example.com" not in query  # Never string-interpolated


def test_get_by_id_found() -> None:
    """Verify get_by_id returns Customer entity when record is found."""
    mock_manager = MagicMock()
    mock_session = MagicMock()
    mock_manager.session.return_value.__enter__.return_value = mock_session

    mock_result = MagicMock()
    mock_result.single.return_value = _mock_customer_record(customer_id="target-id")
    mock_session.run.return_value = mock_result

    repo = CustomerRepository(driver_manager=mock_manager, database="testdb")
    customer = repo.get_by_id("target-id")

    assert customer is not None
    assert customer.id == "target-id"
    assert customer.email == "cust1@example.com"


def test_get_by_id_not_found() -> None:
    """Verify get_by_id returns None when record does not exist."""
    mock_manager = MagicMock()
    mock_session = MagicMock()
    mock_manager.session.return_value.__enter__.return_value = mock_session

    mock_result = MagicMock()
    mock_result.single.return_value = None
    mock_session.run.return_value = mock_result

    repo = CustomerRepository(driver_manager=mock_manager, database="testdb")
    customer = repo.get_by_id("non-existent")

    assert customer is None


def test_get_by_email() -> None:
    """Verify get_by_email returns Customer entity."""
    mock_manager = MagicMock()
    mock_session = MagicMock()
    mock_manager.session.return_value.__enter__.return_value = mock_session

    mock_result = MagicMock()
    mock_result.single.return_value = _mock_customer_record(email="target@example.com")
    mock_session.run.return_value = mock_result

    repo = CustomerRepository(driver_manager=mock_manager, database="testdb")
    customer = repo.get_by_email("target@example.com")

    assert customer is not None
    assert customer.email == "target@example.com"


def test_delete_by_id() -> None:
    """Verify delete_by_id runs DETACH DELETE and returns True on success."""
    mock_manager = MagicMock()
    mock_session = MagicMock()
    mock_manager.session.return_value.__enter__.return_value = mock_session

    mock_result = MagicMock()
    mock_result.single.return_value = {"deleted_count": 1}
    mock_session.run.return_value = mock_result

    repo = CustomerRepository(driver_manager=mock_manager, database="testdb")
    deleted = repo.delete_by_id("cust-to-delete")

    assert deleted is True
    call_args = mock_session.run.call_args
    query, params = call_args[0]
    assert "DETACH DELETE" in query
    assert params["id"] == "cust-to-delete"


def test_database_error_raises_repository_error() -> None:
    """Verify database exceptions are mapped to RepositoryError."""
    mock_manager = MagicMock()
    mock_session = MagicMock()
    mock_manager.session.return_value.__enter__.return_value = mock_session
    mock_session.run.side_effect = Neo4jError("Query execution failed")

    repo = CustomerRepository(driver_manager=mock_manager, database="testdb")
    with pytest.raises(RepositoryError) as exc_info:
        repo.get_by_id("cust-1")

    assert "Database error" in str(exc_info.value)
