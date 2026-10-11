"""Reusable, safe Neo4j Python driver manager for GraphSupport AI.

Manages connection pooling, encrypted Aura transport, deterministic session creation,
and connectivity verification without exposing credentials in logs or exceptions.
"""

import logging
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from neo4j import Driver, GraphDatabase, Session
from neo4j.exceptions import AuthError, ServiceUnavailable
from neo4j.exceptions import ConfigurationError as Neo4jConfigError

from graphsupport.config import get_settings
from graphsupport.config.settings import Settings
from graphsupport.core.exceptions import DatabaseConfigurationError, DatabaseConnectionError

if TYPE_CHECKING:
    from neo4j import ServerInfo

logger = logging.getLogger("graphsupport.graph.driver")


class Neo4jDriverManager:
    """Encapsulates a managed Neo4j Driver instance and connection pooling."""

    def __init__(
        self,
        settings: Settings | None = None,
        max_connection_lifetime_sec: int = 3600,
        connection_timeout_sec: float = 15.0,
        max_connection_pool_size: int = 50,
    ) -> None:
        self.settings = settings or get_settings()
        self.max_connection_lifetime_sec = max_connection_lifetime_sec
        self.connection_timeout_sec = connection_timeout_sec
        self.max_connection_pool_size = max_connection_pool_size
        self._driver: Driver | None = None

    def _validate_configuration(self) -> None:
        """Validate that minimum connection parameters are present."""
        if not self.settings.neo4j_uri:
            raise DatabaseConfigurationError(
                "Neo4j URI is not configured. Please set NEO4J_URI in your environment."
            )
        if not self.settings.neo4j_username:
            raise DatabaseConfigurationError(
                "Neo4j username is not configured. Please set NEO4J_USERNAME in your environment."
            )
        if not self.settings.neo4j_password:
            raise DatabaseConfigurationError(
                "Neo4j password is not configured. Please set NEO4J_PASSWORD in your environment."
            )

    def get_driver(self) -> Driver:
        """Obtain or initialize the active Neo4j driver singleton."""
        if self._driver is not None:
            return self._driver

        self._validate_configuration()

        uri = str(self.settings.neo4j_uri)
        username = str(self.settings.neo4j_username)
        # Extract secret value without printing or logging it
        password = self.settings.neo4j_password.get_secret_value()  # type: ignore[union-attr]

        logger.info(
            "Initializing Neo4j driver (URI: %s, Database: %s, User: %s)...",
            uri,
            self.settings.neo4j_database,
            username,
        )

        try:
            self._driver = GraphDatabase.driver(
                uri,
                auth=(username, password),
                max_connection_lifetime=self.max_connection_lifetime_sec,
                connection_timeout=self.connection_timeout_sec,
                max_connection_pool_size=self.max_connection_pool_size,
            )
            return self._driver
        except (Neo4jConfigError, ValueError) as err:
            raise DatabaseConfigurationError(
                f"Invalid Neo4j driver configuration: {type(err).__name__}: {err}"
            ) from err
        except Exception as err:
            raise DatabaseConnectionError(
                f"Failed to instantiate Neo4j driver: {type(err).__name__}"
            ) from err

    def verify_connectivity(self) -> bool:
        """Explicitly test connection to the Neo4j database using driver verification.

        Returns:
            True if database is reachable and credentials are valid.

        Raises:
            DatabaseConnectionError: If connection cannot be established or credentials fail.
            DatabaseConfigurationError: If required settings are missing.
        """
        driver = self.get_driver()
        try:
            logger.debug("Verifying Neo4j connectivity...")
            driver.verify_connectivity()
            logger.info("Neo4j connectivity successfully verified.")
            return True
        except AuthError as err:
            raise DatabaseConnectionError(
                "Neo4j authentication failed: invalid username or password."
            ) from err
        except ServiceUnavailable as err:
            raise DatabaseConnectionError(
                "Neo4j database service is unavailable or unreachable."
            ) from err
        except Exception as err:
            raise DatabaseConnectionError(
                f"Neo4j connectivity check failed: {type(err).__name__}: {err}"
            ) from err

    def get_server_info(self) -> dict[str, Any]:
        """Retrieve server agent and protocol metadata safely."""
        driver = self.get_driver()
        try:
            info: ServerInfo = driver.get_server_info()
            return {
                "agent": info.agent,
                "protocol_version": f"{info.protocol_version[0]}.{info.protocol_version[1]}",
                "database": self.settings.neo4j_database,
            }
        except Exception as err:
            logger.warning("Could not retrieve Neo4j server info: %s", err)
            return {"error": type(err).__name__}

    @contextmanager
    def session(self, database: str | None = None) -> Generator[Session, None, None]:
        """Context manager yielding a database session for query execution."""
        driver = self.get_driver()
        target_db = database or self.settings.neo4j_database
        session = driver.session(database=target_db)
        try:
            yield session
        finally:
            session.close()

    def close(self) -> None:
        """Close the managed driver and release socket connections."""
        if self._driver is not None:
            logger.info("Closing Neo4j driver connections...")
            try:
                self._driver.close()
            except Exception as err:
                logger.warning("Error encountered while closing driver: %s", err)
            finally:
                self._driver = None


_driver_manager_singleton: Neo4jDriverManager | None = None


def get_driver_manager(settings: Settings | None = None) -> Neo4jDriverManager:
    """Retrieve or create the application-wide Neo4jDriverManager singleton."""
    global _driver_manager_singleton
    if _driver_manager_singleton is None:
        _driver_manager_singleton = Neo4jDriverManager(settings=settings)
    return _driver_manager_singleton


def close_driver_manager() -> None:
    """Close and reset the global driver manager singleton."""
    global _driver_manager_singleton
    if _driver_manager_singleton is not None:
        _driver_manager_singleton.close()
        _driver_manager_singleton = None
