"""Application health check and readiness inspection for GraphSupport AI.

Provides transparent, non-sensitive reporting on system status, initialization state,
runtime environment, and phase readiness without contacting external networks or exposing secrets.
"""

import platform
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from graphsupport.config.settings import Settings


@dataclass(frozen=True)
class ServiceReadiness:
    """Readiness status for an external service dependency."""

    name: str
    target_phase: str
    configured: bool
    status_message: str


@dataclass(frozen=True)
class HealthStatus:
    """Comprehensive, safe application status payload."""

    status: str
    app_name: str
    app_version: str
    environment: str
    current_phase: str
    python_version: str
    platform_info: str
    timestamp: str
    neo4j: ServiceReadiness
    llm: ServiceReadiness

    def to_dict(self) -> dict[str, Any]:
        """Convert status to a serializable dictionary safe for logging and UI display."""
        return asdict(self)


def check_health(settings: "Settings | None" = None) -> HealthStatus:
    """Perform health and readiness check for GraphSupport AI.

    Args:
        settings: Application settings. If omitted, uses active cached settings.

    Returns:
        HealthStatus dataclass reporting initialization and phase state.
    """
    if settings is None:
        from graphsupport.config.settings import get_settings

        app_settings = get_settings()
    else:
        app_settings = settings

    neo4j_readiness = ServiceReadiness(
        name="Neo4j Knowledge Graph",
        target_phase="Phase 2",
        configured=app_settings.is_neo4j_configured,
        status_message=(
            "Parameters configured (connection deferred to Phase 2)"
            if app_settings.is_neo4j_configured
            else "Not configured (Deferred to Phase 2)"
        ),
    )

    llm_readiness = ServiceReadiness(
        name="LLM Provider",
        target_phase="Phase 5",
        configured=app_settings.is_llm_configured,
        status_message=(
            f"Provider '{app_settings.llm_provider}' configured (deferred to Phase 5)"
            if app_settings.is_llm_configured
            else "Not configured (Deferred to Phase 5)"
        ),
    )

    return HealthStatus(
        status="healthy",
        app_name=app_settings.app_name,
        app_version=app_settings.app_version,
        environment=app_settings.app_env.value,
        current_phase="Phase 1: Professional Foundation",
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        platform_info=f"{platform.system()} {platform.machine()}",
        timestamp=datetime.now(UTC).isoformat(),
        neo4j=neo4j_readiness,
        llm=llm_readiness,
    )
