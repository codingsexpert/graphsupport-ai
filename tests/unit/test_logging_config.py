"""Unit tests for structured logging configuration in GraphSupport AI."""

import logging

from graphsupport.config.settings import LogLevel, Settings
from graphsupport.core.logging_config import (
    configure_logging,
    get_logger,
)


def test_configure_logging_with_settings() -> None:
    """Verify logger configuration using a Settings instance."""
    settings = Settings(_env_file=None, log_level=LogLevel.DEBUG)
    logger = configure_logging(settings, force=True)

    assert logger.level == logging.DEBUG
    root = logging.getLogger()
    assert root.level == logging.DEBUG


def test_configure_logging_idempotence() -> None:
    """Verify subsequent calls to configure_logging do not duplicate stream handlers."""
    configure_logging("INFO", force=True)
    initial_handler_count = len(logging.getLogger().handlers)

    configure_logging("INFO", force=False)
    assert len(logging.getLogger().handlers) == initial_handler_count


def test_formatter_has_expected_fields() -> None:
    """Verify log formatter specifies timestamp, level, name, and message."""
    configure_logging("INFO", force=True)
    assert len(logging.getLogger().handlers) > 0
    formatter = logging.getLogger().handlers[0].formatter
    assert formatter is not None
    assert "%(asctime)s" in formatter._fmt
    assert "%(levelname)" in formatter._fmt
    assert "%(name)s" in formatter._fmt
    assert "%(message)s" in formatter._fmt


def test_get_logger_hierarchy() -> None:
    """Verify get_logger returns loggers under the graphsupport namespace."""
    sub_logger = get_logger("core.test_module")
    assert sub_logger.name == "graphsupport.core.test_module"

    root_sub = get_logger("graphsupport.config")
    assert root_sub.name == "graphsupport.config"


def test_secret_sanitizing_filter(caplog) -> None:
    """Verify that accidental inline secrets in log messages are redacted."""
    configure_logging("DEBUG", force=True)
    logger = get_logger("security_test")

    with caplog.at_level(logging.INFO):
        logger.info("Attempting connection with password=super_secret_123 token=abc456")

    assert "super_secret_123" not in caplog.text
    assert "password=[REDACTED]" in caplog.text
