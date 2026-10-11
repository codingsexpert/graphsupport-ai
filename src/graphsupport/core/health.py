"""Application health check and readiness inspection for GraphSupport AI.

Provides transparent, non-sensitive reporting on system status, initialization state,
runtime environment, and phase readiness without exposing credentials or executing
unnecessary network operations during ordinary runs.
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
    reachability: str = "not_checked"
    server_info: dict[str, Any] | None = None


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
    langsmith: ServiceReadiness | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert status to a serializable dictionary safe for logging and UI display."""
        return asdict(self)


def check_health(
    settings: "Settings | None" = None,
    verify_database: bool = False,
) -> HealthStatus:
    """Perform health and readiness check for GraphSupport AI.

    Args:
        settings: Application settings. If omitted, uses active cached settings.
        verify_database: If True, performs live connectivity check against Neo4j.

    Returns:
        HealthStatus dataclass reporting initialization and phase state.
    """
    if settings is None:
        from graphsupport.config.settings import get_settings

        app_settings = get_settings()
    else:
        app_settings = settings

    neo4j_reachability = "not_configured"
    neo4j_server_info: dict[str, Any] | None = None

    if not app_settings.is_neo4j_configured:
        neo4j_msg = "Not configured (Deferred to Phase 2)"
        neo4j_reachability = "not_configured"
    elif verify_database:
        try:
            from graphsupport.graph.driver import get_driver_manager

            dm = get_driver_manager(settings=app_settings)
            dm.verify_connectivity()
            info = dm.get_server_info()
            neo4j_reachability = "reachable"
            neo4j_server_info = info
            neo4j_msg = f"Database reachable ({info.get('agent', 'Neo4j')})"
        except Exception as err:
            neo4j_reachability = "unavailable"
            safe_err = type(err).__name__
            neo4j_msg = f"Database unavailable ({safe_err})"
    else:
        neo4j_msg = "Parameters configured (connection deferred to Phase 2, not checked yet)"
        neo4j_reachability = "not_checked"

    neo4j_readiness = ServiceReadiness(
        name="Neo4j Knowledge Graph",
        target_phase="Phase 2",
        configured=app_settings.is_neo4j_configured,
        status_message=neo4j_msg,
        reachability=neo4j_reachability,
        server_info=neo4j_server_info,
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
        reachability="not_configured" if not app_settings.is_llm_configured else "not_checked",
    )

    langsmith_readiness = ServiceReadiness(
        name="LangSmith Observability",
        target_phase="Observability",
        configured=app_settings.is_langsmith_configured,
        status_message=(
            f"Project '{app_settings.langsmith_project}' active (tracing enabled)"
            if app_settings.is_langsmith_configured
            else "Observability disabled or API key unset (zero overhead offline mode)"
        ),
        reachability="configured" if app_settings.is_langsmith_configured else "disabled",
    )

    return HealthStatus(
        status="healthy",
        app_name=app_settings.app_name,
        app_version=app_settings.app_version,
        environment=app_settings.app_env.value,
        current_phase="Phase 2: Neo4j Graph Schema & Storage (built upon Phase 1 Foundation)",
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        platform_info=f"{platform.system()} {platform.machine()}",
        timestamp=datetime.now(UTC).isoformat(),
        neo4j=neo4j_readiness,
        llm=llm_readiness,
        langsmith=langsmith_readiness,
    )
