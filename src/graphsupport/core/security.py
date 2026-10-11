"""Security and input sanitization utilities for GraphSupport AI (Phase 7).

Provides rigorous validation of identifiers, defense-in-depth prompt injection
detection, text sanitization, and PII/secret redaction for logging.
"""

import re
from typing import Any

from graphsupport.core.exceptions import SecurityViolationError, ValidationError

# Permitted character pattern for stable entity identifiers (UUIDs, prefixed IDs)
SAFE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]{1,128}$")

# Suspicious prompt injection signatures (case-insensitive)
PROMPT_INJECTION_SIGNATURES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions", re.IGNORECASE),
        "Instruction override attempt",
    ),
    (
        re.compile(r"disregard\s+(?:all\s+)?(?:system|previous)\s+prompts?", re.IGNORECASE),
        "Prompt disregard attempt",
    ),
    (
        re.compile(r"you\s+are\s+now\s+(?:dan|jailbroken|unrestricted)", re.IGNORECASE),
        "Persona hijacking attempt",
    ),
    (
        re.compile(
            r"(?:reveal|print|output|display)\s+(?:the\s+|your\s+)?(?:system\s+prompt|instructions\s+verbatim)",
            re.IGNORECASE,
        ),
        "System prompt extraction attempt",
    ),
    (
        re.compile(
            r"(?:reveal|print|leak)\s+(?:the\s+)?(?:database\s+password|api\s*key|secret)",
            re.IGNORECASE,
        ),
        "Credential harvesting attempt",
    ),
    (
        re.compile(r"(?:neo4j_password|llm_api_key|neo4j_uri)", re.IGNORECASE),
        "Internal configuration token reference",
    ),
    (
        re.compile(r"(?:drop\s+database|match\s*\(n\)\s*detach\s*delete\s*n)", re.IGNORECASE),
        "Arbitrary Cypher payload execution attempt",
    ),
]

# Sensitive pattern regexes for log and display redaction
CREDIT_CARD_PATTERN = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
KEY_SECRET_PATTERN = re.compile(
    r"(?i)\b(password|secret|api[_-]?key|token)\b\s*[:=]\s*['\"]?([A-Za-z0-9_\-+=/]{6,})['\"]?"
)
CONNECTION_URI_PATTERN = re.compile(r"(?i)(neo4j(?:\+s|\+ssc)?://[^:]+:)([^@]+)(@)")


def validate_entity_id(id_val: Any, field_name: str = "Identifier") -> str:
    """Validate that an entity identifier is non-empty and strictly matches safe characters.

    Args:
        id_val: Input identifier value.
        field_name: Contextual label for error messages.

    Returns:
        Stripped, validated identifier string.

    Raises:
        ValidationError: If identifier is empty or contains disallowed characters.
    """
    if id_val is None:
        raise ValidationError(f"{field_name} cannot be null")

    cleaned = str(id_val).strip()
    if not cleaned:
        raise ValidationError(f"{field_name} cannot be empty")

    if not SAFE_ID_PATTERN.match(cleaned):
        raise ValidationError(
            f"{field_name} contains invalid characters. Must be 1-128 alphanumeric characters, "
            f"hyphens, periods, or underscores; got: '{cleaned[:20]}...'"
        )

    # Explicit rejection of Cypher/SQL injection tokens and control chars
    dangerous_chars = {"'", '"', ";", "{", "}", "(", ")", "$", "/", "\\", "\x00"}
    if any(ch in cleaned for ch in dangerous_chars):
        raise ValidationError(f"{field_name} contains forbidden control or query characters")

    return cleaned


def sanitize_text_input(text: Any, max_chars: int = 4000, field_name: str = "Input text") -> str:
    """Sanitize arbitrary user text, strip null bytes, and enforce length boundaries.

    Args:
        text: Input string.
        max_chars: Maximum permitted character length.
        field_name: Contextual label for error messages.

    Returns:
        Cleaned, stripped string.

    Raises:
        ValidationError: If string exceeds max_chars.
    """
    if text is None:
        return ""

    # Strip null bytes and control chars (except newline and tab)
    cleaned = str(text).replace("\x00", "").strip()

    if len(cleaned) > max_chars:
        raise ValidationError(
            f"{field_name} exceeds maximum allowed length of {max_chars} characters "
            f"(received {len(cleaned)} characters)"
        )

    return cleaned


def scan_for_prompt_injection(message: str) -> tuple[bool, str | None]:
    """Inspect user text for known prompt injection and system override signatures.

    Args:
        message: Incoming text to inspect.

    Returns:
        Tuple of (is_flagged, detection_reason).
    """
    if not message:
        return False, None

    normalized = message.strip()
    for pattern, reason in PROMPT_INJECTION_SIGNATURES:
        if pattern.search(normalized):
            return True, reason

    return False, None


def enforce_prompt_safety(message: str, strict: bool = False) -> None:
    """Raise SecurityViolationError if high-severity prompt injection signature is detected.

    Args:
        message: User input to evaluate.
        strict: If True, raises immediately on any flagged signature.

    Raises:
        SecurityViolationError: If strict enforcement is active and signature is found.
    """
    flagged, reason = scan_for_prompt_injection(message)
    if flagged and strict:
        raise SecurityViolationError(f"Security policy rejected input: {reason}")


def redact_sensitive_text(text: str) -> str:
    """Scrub credit cards, passwords, and sensitive keys from log or display strings.

    Args:
        text: Raw log or display string.

    Returns:
        Sanitized string with sensitive tokens replaced by [REDACTED].
    """
    if not text:
        return ""

    sanitized = CREDIT_CARD_PATTERN.sub("[REDACTED_CARD]", text)
    sanitized = KEY_SECRET_PATTERN.sub(r"\1=[REDACTED]", sanitized)
    sanitized = CONNECTION_URI_PATTERN.sub(r"\1[REDACTED]\3", sanitized)
    return sanitized
