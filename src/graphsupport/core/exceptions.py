"""Exception hierarchy for GraphSupport AI.

Provides structured, domain-specific exception types to prevent broad
exception swallowing and ensure actionable error messages across subsystems.
"""

from typing import Any


class GraphSupportError(Exception):
    """Base exception for all application-level GraphSupport AI errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (details: {self.details})"
        return self.message


class ConfigurationError(GraphSupportError):
    """Raised when application configuration is missing, invalid, or malformed."""


class EnvironmentValidationError(GraphSupportError):
    """Raised when runtime environment (Python, OS, packages) fails requirements."""


class ServiceUnavailableError(GraphSupportError):
    """Raised when an external dependency or service cannot be reached."""


class PhaseNotImplementedError(GraphSupportError):
    """Raised when functionality planned for a future implementation phase is invoked."""


# --- Database & Graph Persistence Exceptions ---


class DatabaseError(GraphSupportError):
    """Base exception for Neo4j database and graph operations."""


class DatabaseConfigurationError(DatabaseError):
    """Raised when database connection settings or credentials are missing/invalid."""


class DatabaseConnectionError(DatabaseError):
    """Raised when connecting to Neo4j fails, times out, or encounters authentication issues."""


class SchemaError(DatabaseError):
    """Raised when graph schema migration, constraint, or index application fails."""


class RepositoryError(DatabaseError):
    """Raised when executing repository operations or Cypher queries fails."""


class EntityNotFoundError(RepositoryError):
    """Raised when an expected graph entity is not found by ID or lookup key."""
