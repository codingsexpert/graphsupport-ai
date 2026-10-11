"""Structured logging configuration for GraphSupport AI.

Ensures predictable, formatted log records across all modules with ISO timestamps,
proper log levels, and module origin. Prevents sensitive data leakage.
"""

import logging
import sys
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from graphsupport.config.settings import LogLevel, Settings

DEFAULT_LOG_FORMAT = "[%(asctime)s] [%(levelname)-8s] [%(name)s:%(lineno)d] %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


class SecretSanitizingFilter(logging.Filter):
    """Logging filter that redacts common sensitive tokens if encountered in log records."""

    SENSITIVE_PATTERNS = ("password", "api_key", "secret", "token", "auth")

    def filter(self, record: logging.LogRecord) -> bool:
        # Guarantee that standard formatting won't fail
        msg = str(record.getMessage())
        for pattern in self.SENSITIVE_PATTERNS:
            if pattern in msg.lower() and "=" in msg:
                # Basic safety masking for accidental inline credential prints
                parts = msg.split()
                sanitized_parts = []
                for p in parts:
                    lower_p = p.lower()
                    if any(s in lower_p for s in self.SENSITIVE_PATTERNS) and "=" in p:
                        key, _ = p.split("=", 1)
                        sanitized_parts.append(f"{key}=[REDACTED]")
                    else:
                        sanitized_parts.append(p)
                record.msg = " ".join(sanitized_parts)
                record.args = ()
        return True


def configure_logging(
    settings_or_level: Union["Settings", "LogLevel", str, None] = None,
    force: bool = False,
) -> logging.Logger:
    """Configure root and application logging with structured formatting.

    Args:
        settings_or_level: A Settings object, LogLevel enum, or log level string.
                           Defaults to INFO if None.
        force: If True, re-configures handlers even if already configured.

    Returns:
        Root logger for GraphSupport AI.
    """
    global _configured

    if _configured and not force:
        return logging.getLogger("graphsupport")

    level_name: str
    if hasattr(settings_or_level, "log_level"):
        lvl = settings_or_level.log_level
        level_name = lvl.value if hasattr(lvl, "value") else str(lvl)
    elif hasattr(settings_or_level, "value"):
        level_name = str(settings_or_level.value)
    elif isinstance(settings_or_level, str):
        level_name = settings_or_level.upper()
    else:
        level_name = "INFO"

    numeric_level = getattr(logging, level_name, logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing graphsupport handlers to ensure idempotence
    handlers_to_remove = [
        h for h in root_logger.handlers if getattr(h, "_graphsupport_handler", False)
    ]
    for h in handlers_to_remove:
        root_logger.removeHandler(h)

    # If root logger has no handlers, create a stdout StreamHandler
    if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(numeric_level)
        formatter = logging.Formatter(fmt=DEFAULT_LOG_FORMAT, datefmt=DEFAULT_DATE_FORMAT)
        handler.setFormatter(formatter)
        handler.addFilter(SecretSanitizingFilter())
        handler._graphsupport_handler = True  # type: ignore[attr-defined]
        root_logger.addHandler(handler)
    else:
        # Update existing handlers with our formatter and filter
        for h in root_logger.handlers:
            h.setLevel(numeric_level)
            h.setFormatter(logging.Formatter(fmt=DEFAULT_LOG_FORMAT, datefmt=DEFAULT_DATE_FORMAT))
            h.addFilter(SecretSanitizingFilter())

    # Ensure third-party noisy loggers don't flood
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    _configured = True
    app_logger = logging.getLogger("graphsupport")
    app_logger.setLevel(numeric_level)
    return app_logger


def get_logger(name: str) -> logging.Logger:
    """Convenience helper to obtain a named logger under the graphsupport namespace."""
    if not _configured:
        configure_logging()
    if name.startswith("graphsupport"):
        return logging.getLogger(name)
    return logging.getLogger(f"graphsupport.{name}")
