"""Core functionality for GraphSupport AI."""

from graphsupport.core.exceptions import (
    AuthorizationError,
    ConfigurationError,
    DatabaseConfigurationError,
    DatabaseConnectionError,
    DatabaseError,
    DuplicateEntityError,
    EntityNotFoundError,
    EnvironmentValidationError,
    GraphSupportError,
    PhaseNotImplementedError,
    RelationshipError,
    RepositoryError,
    SchemaError,
    ServiceUnavailableError,
    ValidationError,
)
from graphsupport.core.health import HealthStatus, check_health
from graphsupport.core.logging_config import configure_logging

__all__ = [
    "GraphSupportError",
    "ConfigurationError",
    "EnvironmentValidationError",
    "ServiceUnavailableError",
    "PhaseNotImplementedError",
    "ValidationError",
    "AuthorizationError",
    "DatabaseError",
    "DatabaseConfigurationError",
    "DatabaseConnectionError",
    "SchemaError",
    "RepositoryError",
    "EntityNotFoundError",
    "DuplicateEntityError",
    "RelationshipError",
    "configure_logging",
    "HealthStatus",
    "check_health",
]
