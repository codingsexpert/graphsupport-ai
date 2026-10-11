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
    RateLimitExceededError,
    RelationshipError,
    RepositoryError,
    SchemaError,
    SecurityViolationError,
    ServiceUnavailableError,
    ValidationError,
)
from graphsupport.core.health import HealthStatus, check_health
from graphsupport.core.logging_config import configure_logging
from graphsupport.core.rate_limiter import InMemoryRateLimiter, get_rate_limiter
from graphsupport.core.security import (
    enforce_prompt_safety,
    redact_sensitive_text,
    sanitize_text_input,
    scan_for_prompt_injection,
    validate_entity_id,
)

__all__ = [
    "GraphSupportError",
    "ConfigurationError",
    "EnvironmentValidationError",
    "ServiceUnavailableError",
    "PhaseNotImplementedError",
    "ValidationError",
    "AuthorizationError",
    "RateLimitExceededError",
    "SecurityViolationError",
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
    "InMemoryRateLimiter",
    "get_rate_limiter",
    "validate_entity_id",
    "sanitize_text_input",
    "scan_for_prompt_injection",
    "enforce_prompt_safety",
    "redact_sensitive_text",
]
