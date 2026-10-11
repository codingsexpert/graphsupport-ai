"""Application configuration management for GraphSupport AI.

Utilizes Pydantic Settings to provide typed, validated, and secure configuration
loading from environment variables and .env files. Sensitive credentials use
SecretStr and are masked from logs and representations.
"""

from enum import StrEnum
from functools import lru_cache
from typing import Any

from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from graphsupport.core.exceptions import ConfigurationError


class AppEnvironment(StrEnum):
    """Supported execution environments."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    """Supported logging levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    """Typed application settings with secure secret handling."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Core Application Settings
    app_name: str = Field(default="GraphSupport AI", description="Application display name")
    app_version: str = Field(default="0.1.0", description="Semantic application version")
    app_env: AppEnvironment = Field(
        default=AppEnvironment.DEVELOPMENT,
        description="Current runtime environment (development, testing, production)",
    )
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Application logging verbosity",
    )

    # Streamlit Defaults
    streamlit_server_port: int = Field(
        default=8501,
        description="Default Streamlit HTTP server port",
    )
    streamlit_server_headless: bool = Field(
        default=True,
        description="Run Streamlit in headless mode without launching browser automatically",
    )

    # Neo4j Graph Database (Reserved for Phase 2)
    neo4j_uri: str | None = Field(
        default=None,
        description="Neo4j connection URI (e.g. bolt://localhost:7687 or neo4j+s://...)",
    )
    neo4j_username: str | None = Field(
        default=None,
        description="Neo4j username for authentication",
    )
    neo4j_password: SecretStr | None = Field(
        default=None,
        description="Neo4j password (masked to prevent credential leakage)",
    )
    neo4j_database: str = Field(
        default="neo4j",
        description="Target Neo4j database name",
    )

    # LLM Provider Configuration
    llm_provider: str | None = Field(
        default=None,
        description="LLM provider name (e.g., google, openai, sarvam, mock)",
    )
    llm_api_key: SecretStr | None = Field(
        default=None,
        description="API key for selected LLM provider (masked)",
    )
    llm_model: str | None = Field(
        default=None,
        description="Specific model identifier (e.g., gemini-2.0-flash, gpt-4o, sarvam-105b)",
    )

    # Sarvam AI Configuration (Indian LLM & Multilingual)
    sarvam_api_key: SecretStr | None = Field(
        default=None,
        description="Sarvam AI API subscription key (masked)",
    )
    sarvam_model: str = Field(
        default="sarvam-105b-conversations",
        description="Sarvam AI model identifier (e.g. sarvam-105b-conversations, sarvam-105b)",
    )
    sarvam_base_url: str = Field(
        default="https://api.sarvam.ai/v1",
        description="Sarvam AI API base URL",
    )

    # LangSmith Observability Configuration
    langsmith_tracing: bool = Field(
        default=False,
        description="Enable LangSmith tracing for agent reasoning and tool executions",
    )
    langsmith_api_key: SecretStr | None = Field(
        default=None,
        description="LangSmith API key for trace ingestion (masked)",
    )
    langsmith_project: str = Field(
        default="graphsupport-ai",
        description="LangSmith project name",
    )
    langsmith_endpoint: str = Field(
        default="https://api.smith.langchain.com",
        description="LangSmith API endpoint",
    )

    @field_validator("streamlit_server_port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate server port is in valid range."""
        if not (1024 <= v <= 65535):
            raise ValueError(f"Streamlit server port must be between 1024 and 65535, got {v}")
        return v

    @property
    def is_neo4j_configured(self) -> bool:
        """Check if minimum Neo4j connection parameters are present."""
        return bool(self.neo4j_uri and self.neo4j_username and self.neo4j_password)

    @property
    def is_llm_configured(self) -> bool:
        """Check if minimum LLM provider parameters are present."""
        if not self.llm_provider:
            return False
        p = self.llm_provider.strip().lower()
        if p == "mock":
            return True
        if p == "sarvam":
            return bool(self.sarvam_api_key or self.llm_api_key)
        return bool(self.llm_api_key)

    @property
    def is_langsmith_configured(self) -> bool:
        """Check if LangSmith tracing is active and configured with credentials."""
        return bool(self.langsmith_tracing and self.langsmith_api_key)

    def safe_summary(self) -> dict[str, Any]:
        """Return non-sensitive configuration summary safe for display and logging.

        Secrets are masked or reported as boolean presence indicators.
        """
        return {
            "app_name": self.app_name,
            "app_version": self.app_version,
            "app_env": self.app_env.value,
            "log_level": self.log_level.value,
            "streamlit_server_port": self.streamlit_server_port,
            "streamlit_server_headless": self.streamlit_server_headless,
            "neo4j": {
                "configured": self.is_neo4j_configured,
                "uri": self.neo4j_uri or "[NOT CONFIGURED]",
                "database": self.neo4j_database,
                "username": self.neo4j_username or "[NOT CONFIGURED]",
                "password_set": self.neo4j_password is not None,
                "phase_status": "Reserved for Phase 2",
            },
            "llm": {
                "configured": self.is_llm_configured,
                "provider": self.llm_provider or "[NOT CONFIGURED]",
                "model": self.llm_model or "[NOT CONFIGURED]",
                "api_key_set": bool(self.llm_api_key or self.sarvam_api_key),
                "phase_status": "Reserved for Phase 5",
            },
            "sarvam": {
                "configured": bool(
                    self.sarvam_api_key or (self.llm_provider == "sarvam" and self.llm_api_key)
                ),
                "model": self.sarvam_model,
                "base_url": self.sarvam_base_url,
                "api_key_set": self.sarvam_api_key is not None,
            },
            "langsmith": {
                "configured": self.is_langsmith_configured,
                "tracing_enabled": self.langsmith_tracing,
                "project": self.langsmith_project,
                "endpoint": self.langsmith_endpoint,
                "api_key_set": self.langsmith_api_key is not None,
            },
        }


def create_settings(**kwargs: Any) -> Settings:
    """Create a Settings instance with validation error translation.

    Converts Pydantic ValidationErrors into domain-specific ConfigurationError
    with actionable context.
    """
    try:
        return Settings(**kwargs)
    except ValidationError as err:
        error_messages = []
        for error in err.errors():
            loc = ".".join(str(p) for p in error.get("loc", []))
            msg = error.get("msg", "invalid value")
            error_messages.append(f"Field '{loc}': {msg}")
        raise ConfigurationError(
            f"Configuration validation failed: {'; '.join(error_messages)}",
            details={"errors": err.errors()},
        ) from err


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retrieve cached application settings singleton."""
    return create_settings()


def reload_settings(**overrides: Any) -> Settings:
    """Clear cache and reload settings, optionally applying overrides (useful for testing)."""
    get_settings.cache_clear()
    if overrides:
        return create_settings(**overrides)
    return get_settings()
