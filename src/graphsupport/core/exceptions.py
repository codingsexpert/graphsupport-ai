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
