"""Unit tests for Neo4j driver manager and connectivity handling."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from graphsupport.config.settings import Settings
from graphsupport.core.exceptions import DatabaseConfigurationError, DatabaseConnectionError
from graphsupport.graph.driver import (
    Neo4jDriverManager,
    close_driver_manager,
    get_driver_manager,
)


def test_driver_manager_missing_credentials_raises_configuration_error() -> None:
    """Verify that unconfigured credentials fail with actionable DatabaseConfigurationError."""
    empty_settings = Settings(
        _env_file=None, neo4j_uri=None, neo4j_username=None, neo4j_password=None
    )
    manager = Neo4jDriverManager(settings=empty_settings)

    with pytest.raises(DatabaseConfigurationError) as exc_info:
        manager.get_driver()

    assert "NEO4J_URI" in str(exc_info.value)


def test_driver_manager_secret_safety_in_errors() -> None:
    """Verify that secret passwords are never exposed in exception strings or representations."""
    raw_pass = "super_classified_graph_pwd"
    settings = Settings(
        _env_file=None,
        neo4j_uri="bolt://localhost:7687",
        neo4j_username="neo4j",
        neo4j_password=SecretStr(raw_pass),
    )
    manager = Neo4jDriverManager(settings=settings)

    with patch("neo4j.GraphDatabase.driver", side_effect=Exception("Connection refused")):
        with pytest.raises(DatabaseConnectionError) as exc_info:
            manager.get_driver()

        error_message = str(exc_info.value)
        assert raw_pass not in error_message


def test_verify_connectivity_success() -> None:
    """Verify verify_connectivity returns True when driver check passes."""
    settings = Settings(
        _env_file=None,
        neo4j_uri="bolt://localhost:7687",
        neo4j_username="neo4j",
        neo4j_password=SecretStr("pwd"),
    )
    manager = Neo4jDriverManager(settings=settings)

    mock_driver = MagicMock()
    mock_driver.verify_connectivity.return_value = None
    manager._driver = mock_driver

    assert manager.verify_connectivity() is True
    mock_driver.verify_connectivity.assert_called_once()


def test_verify_connectivity_failure_raises_database_connection_error() -> None:
    """Verify verify_connectivity translates driver errors into DatabaseConnectionError."""
    settings = Settings(
        _env_file=None,
        neo4j_uri="bolt://localhost:7687",
        neo4j_username="neo4j",
        neo4j_password=SecretStr("pwd"),
    )
    manager = Neo4jDriverManager(settings=settings)

    mock_driver = MagicMock()
    mock_driver.verify_connectivity.side_effect = Exception("Network unreachable")
    manager._driver = mock_driver

    with pytest.raises(DatabaseConnectionError) as exc_info:
        manager.verify_connectivity()

    assert "connectivity check failed" in str(exc_info.value)


def test_session_context_manager() -> None:
    """Verify session context manager yields session and closes it cleanly."""
    settings = Settings(
        _env_file=None,
        neo4j_uri="bolt://localhost:7687",
        neo4j_username="neo4j",
        neo4j_password=SecretStr("pwd"),
    )
    manager = Neo4jDriverManager(settings=settings)

    mock_session = MagicMock()
    mock_driver = MagicMock()
    mock_driver.session.return_value = mock_session
    manager._driver = mock_driver

    with manager.session(database="test_db") as sess:
        assert sess is mock_session
        mock_driver.session.assert_called_once_with(database="test_db")

    mock_session.close.assert_called_once()


def test_driver_lifecycle_close() -> None:
    """Verify close cleanly terminates active driver."""
    settings = Settings(
        _env_file=None,
        neo4j_uri="bolt://localhost:7687",
        neo4j_username="neo4j",
        neo4j_password=SecretStr("pwd"),
    )
    manager = Neo4jDriverManager(settings=settings)
    mock_driver = MagicMock()
    manager._driver = mock_driver

    manager.close()
    mock_driver.close.assert_called_once()
    assert manager._driver is None


def test_global_driver_manager_singleton() -> None:
    """Verify get_driver_manager returns singleton and close_driver_manager resets it."""
    dm1 = get_driver_manager()
    dm2 = get_driver_manager()
    assert dm1 is dm2

    close_driver_manager()
    dm3 = get_driver_manager()
    assert dm3 is not dm1
    close_driver_manager()
