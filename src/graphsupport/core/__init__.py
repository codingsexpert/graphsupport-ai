"""Core functionality for GraphSupport AI."""

from graphsupport.core.exceptions import (
    ConfigurationError,
    DatabaseConfigurationError,
    DatabaseConnectionError,
    DatabaseError,
    EntityNotFoundError,
    EnvironmentValidationError,
    GraphSupportError,
    PhaseNotImplementedError,
    RepositoryError,
    SchemaError,
    ServiceUnavailableError,
)
from graphsupport.core.health import HealthStatus, check_health
from graphsupport.core.logging_config import configure_logging

__all__ = [
    "GraphSupportError",
    "ConfigurationError",
    "EnvironmentValidationError",
    "ServiceUnavailableError",
    "PhaseNotImplementedError",
    "DatabaseError",
    "DatabaseConfigurationError",
    "DatabaseConnectionError",
    "SchemaError",
    "RepositoryError",
    "EntityNotFoundError",
    "configure_logging",
    "HealthStatus",
    "check_health",
]
