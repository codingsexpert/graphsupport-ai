"""Unit tests for system health inspection and readiness reporting."""

from graphsupport.config.settings import Settings
from graphsupport.core.health import check_health


def test_health_check_default_configuration() -> None:
    """Verify health check returns expected status with default unconfigured services."""
    settings = Settings(_env_file=None)
    health = check_health(settings)

    assert health.status == "healthy"
    assert health.app_name == "GraphSupport AI"
    assert health.app_version == "0.1.0"
    assert health.environment == "development"
    assert "Phase 1" in health.current_phase
    assert health.python_version != ""
    assert health.platform_info != ""
    assert "T" in health.timestamp  # Valid ISO timestamp

    # Reserved service readiness must be safely marked as unconfigured
    assert health.neo4j.configured is False
    assert health.neo4j.target_phase == "Phase 2"
    assert "Deferred to Phase 2" in health.neo4j.status_message

    assert health.llm.configured is False
    assert health.llm.target_phase == "Phase 5"
    assert "Deferred to Phase 5" in health.llm.status_message


def test_health_check_configured_services() -> None:
    """Verify readiness flags update properly when service parameters are supplied."""
    settings = Settings(
        _env_file=None,
        neo4j_uri="bolt://localhost:7687",
        neo4j_username="neo4j",
        neo4j_password="secretpassword",
        llm_provider="google",
        llm_api_key="secretkey",
    )
    health = check_health(settings)

    assert health.neo4j.configured is True
    assert "deferred to Phase 2" in health.neo4j.status_message

    assert health.llm.configured is True
    assert "deferred to Phase 5" in health.llm.status_message


def test_health_dict_contains_no_secrets() -> None:
    """Verify serialization does not expose sensitive credentials."""
    raw_password = "super_private_pass_777"
    raw_api_key = "super_private_key_555"

    settings = Settings(
        _env_file=None,
        neo4j_uri="bolt://localhost:7687",
        neo4j_username="neo4j",
        neo4j_password=raw_password,
        llm_provider="google",
        llm_api_key=raw_api_key,
    )
    health = check_health(settings)
    health_dict = health.to_dict()

    serialized = str(health_dict)
    assert raw_password not in serialized
    assert raw_api_key not in serialized

    assert health_dict["status"] == "healthy"
    assert health_dict["neo4j"]["configured"] is True
    assert health_dict["llm"]["configured"] is True
