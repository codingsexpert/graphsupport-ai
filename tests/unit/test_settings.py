"""Unit tests for configuration loading and validation in GraphSupport AI."""

import pytest

from graphsupport.config.settings import (
    AppEnvironment,
    LogLevel,
    Settings,
    create_settings,
    get_settings,
    reload_settings,
)
from graphsupport.core.exceptions import ConfigurationError


def test_default_settings() -> None:
    """Verify safe default settings when no environment variables are provided."""
    settings = Settings(_env_file=None)

    assert settings.app_name == "GraphSupport AI"
    assert settings.app_version == "0.1.0"
    assert settings.app_env == AppEnvironment.DEVELOPMENT
    assert settings.log_level == LogLevel.INFO
    assert settings.streamlit_server_port == 8501
    assert settings.streamlit_server_headless is True

    # Reserved optional services must be unconfigured by default
    assert settings.neo4j_uri is None
    assert settings.neo4j_username is None
    assert settings.neo4j_password is None
    assert settings.is_neo4j_configured is False

    assert settings.llm_provider is None
    assert settings.llm_api_key is None
    assert settings.is_llm_configured is False


def test_valid_custom_settings() -> None:
    """Verify settings initialization with custom valid arguments."""
    settings = Settings(
        _env_file=None,
        app_name="Test Support",
        app_version="2.0.0",
        app_env="testing",
        log_level="DEBUG",
        streamlit_server_port=9000,
        neo4j_uri="bolt://localhost:7687",
        neo4j_username="admin",
        neo4j_password="supersecretpassword",
        llm_provider="google",
        llm_api_key="ai-test-key",
        llm_model="gemini-2.0-flash",
    )

    assert settings.app_name == "Test Support"
    assert settings.app_version == "2.0.0"
    assert settings.app_env == AppEnvironment.TESTING
    assert settings.log_level == LogLevel.DEBUG
    assert settings.streamlit_server_port == 9000
    assert settings.is_neo4j_configured is True
    assert settings.is_llm_configured is True


def test_invalid_app_env_raises_configuration_error() -> None:
    """Verify that an invalid APP_ENV raises a clear ConfigurationError."""
    with pytest.raises(ConfigurationError) as exc_info:
        create_settings(_env_file=None, app_env="invalid_environment")

    assert "Configuration validation failed" in str(exc_info.value)
    assert "app_env" in str(exc_info.value)


def test_invalid_log_level_raises_configuration_error() -> None:
    """Verify that an invalid LOG_LEVEL raises a ConfigurationError."""
    with pytest.raises(ConfigurationError) as exc_info:
        create_settings(_env_file=None, log_level="SUPER_VERBOSE")

    assert "Configuration validation failed" in str(exc_info.value)
    assert "log_level" in str(exc_info.value)


def test_invalid_port_range_raises_configuration_error() -> None:
    """Verify that a port outside valid range raises a ConfigurationError."""
    with pytest.raises(ConfigurationError) as exc_info:
        create_settings(_env_file=None, streamlit_server_port=80)

    assert "Configuration validation failed" in str(exc_info.value)
    assert "streamlit_server_port" in str(exc_info.value)


def test_secret_masking() -> None:
    """Verify that SecretStr prevents plain-text credential leaks in str/repr."""
    raw_password = "my_top_secret_graph_password"
    raw_api_key = "sk-ai-secret-key-12345"

    settings = Settings(
        _env_file=None,
        neo4j_password=raw_password,
        llm_api_key=raw_api_key,
    )

    # Neither str() nor repr() of SecretStr or Settings should expose raw secrets
    assert raw_password not in str(settings.neo4j_password)
    assert raw_password not in repr(settings.neo4j_password)
    assert "**********" in str(settings.neo4j_password)

    assert raw_api_key not in str(settings.llm_api_key)
    assert raw_api_key not in repr(settings.llm_api_key)
    assert "**********" in str(settings.llm_api_key)

    # But secret can be retrieved explicitly via get_secret_value when needed
    assert settings.neo4j_password is not None
    assert settings.neo4j_password.get_secret_value() == raw_password


def test_safe_summary_does_not_leak_secrets() -> None:
    """Verify that safe_summary() never contains unmasked credentials."""
    raw_password = "neo4j_sensitive_pass_999"
    raw_api_key = "gemini_secret_api_key_888"

    settings = Settings(
        _env_file=None,
        neo4j_uri="bolt://localhost:7687",
        neo4j_username="neo4j",
        neo4j_password=raw_password,
        llm_provider="google",
        llm_api_key=raw_api_key,
    )

    summary = settings.safe_summary()

    # Convert entire summary structure to string to check for leaks
    summary_str = str(summary)
    assert raw_password not in summary_str
    assert raw_api_key not in summary_str

    # Check structural presence indicators
    assert summary["neo4j"]["configured"] is True
    assert summary["neo4j"]["password_set"] is True
    assert summary["neo4j"]["phase_status"] == "Reserved for Phase 2"

    assert summary["llm"]["configured"] is True
    assert summary["llm"]["api_key_set"] is True
    assert summary["llm"]["phase_status"] == "Reserved for Phase 5"


def test_env_variable_loading(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify loading settings from process environment variables."""
    monkeypatch.setenv("APP_NAME", "Env Loaded Support")
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("STREAMLIT_SERVER_PORT", "8555")

    settings = Settings(_env_file=None)
    assert settings.app_name == "Env Loaded Support"
    assert settings.app_env == AppEnvironment.TESTING
    assert settings.log_level == LogLevel.WARNING
    assert settings.streamlit_server_port == 8555


def test_get_and_reload_settings() -> None:
    """Verify settings singleton caching and reload mechanism."""
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2

    reloaded = reload_settings(_env_file=None, app_name="Reloaded App")
    assert reloaded.app_name == "Reloaded App"

    # Reset cache to default
    reload_settings(_env_file=None)
