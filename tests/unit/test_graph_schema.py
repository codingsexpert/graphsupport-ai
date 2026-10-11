"""Unit tests for Neo4j schema initialization and inspection."""

from unittest.mock import MagicMock

from graphsupport.graph.schema import (
    SCHEMA_STATEMENTS,
    initialize_schema,
    inspect_schema,
)


def test_schema_statements_definitions() -> None:
    """Verify that all core constraints and indexes are declared in SCHEMA_STATEMENTS."""
    names = [name for name, _ in SCHEMA_STATEMENTS]

    # Required unique constraints
    assert "customer_id_unique" in names
    assert "customer_email_unique" in names
    assert "product_id_unique" in names
    assert "issue_id_unique" in names
    assert "ticket_id_unique" in names
    assert "conversation_id_unique" in names
    assert "message_id_unique" in names
    assert "step_id_unique" in names
    assert "resolution_id_unique" in names

    # Required indexes
    assert "ticket_status_idx" in names
    assert "product_sku_idx" in names

    # All statements must use IF NOT EXISTS for idempotence
    for _, cypher in SCHEMA_STATEMENTS:
        assert "IF NOT EXISTS" in cypher


def test_initialize_schema_success() -> None:
    """Verify initialize_schema executes each DDL statement."""
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__.return_value = mock_session

    report = initialize_schema(mock_driver, database="testdb")

    assert report.total == len(SCHEMA_STATEMENTS)
    assert report.succeeded == len(SCHEMA_STATEMENTS)
    assert report.failed == 0
    assert report.is_successful is True
    assert mock_session.run.call_count == len(SCHEMA_STATEMENTS)


def test_initialize_schema_partial_failure() -> None:
    """Verify initialize_schema records failed statements without crashing."""
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__.return_value = mock_session

    # Fail the second statement
    def mock_run(stmt: str) -> MagicMock:
        if "customer_email_unique" in stmt:
            raise Exception("Syntax error or permission denied")
        return MagicMock()

    mock_session.run.side_effect = mock_run

    report = initialize_schema(mock_driver, database="testdb")

    assert report.total == len(SCHEMA_STATEMENTS)
    assert report.succeeded == len(SCHEMA_STATEMENTS) - 1
    assert report.failed == 1
    assert report.is_successful is False

    failed_item = next(r for r in report.results if not r.success)
    assert failed_item.name == "customer_email_unique"
    assert "Syntax error" in str(failed_item.error)


def test_inspect_schema() -> None:
    """Verify inspect_schema extracts constraint and index names."""
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__.return_value = mock_session

    mock_session.run.side_effect = [
        [{"name": "customer_id_unique"}],  # SHOW CONSTRAINTS
        [{"name": "ticket_status_idx"}],  # SHOW INDEXES
    ]

    result = inspect_schema(mock_driver, database="testdb")
    assert result["database"] == "testdb"
    assert result["constraints"] == ["customer_id_unique"]
    assert result["indexes"] == ["ticket_status_idx"]
