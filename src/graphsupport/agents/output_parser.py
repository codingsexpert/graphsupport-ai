"""Response validation and output sanitization layer for GraphSupport AI (Phase 5).

Validates agent response structure, enforces length limits, strips leaking internal
tool payloads or credentials, checks factual status claims against ground-truth context,
and provides safe, unhallucinated fallback responses upon validation failure.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from graphsupport.memory.models import CustomerMemoryContext

logger = logging.getLogger("graphsupport.agents.output_parser")

INTERNAL_LEAK_PATTERNS = [
    re.compile(r"systemInstruction", re.IGNORECASE),
    re.compile(r"functionDeclarations", re.IGNORECASE),
    re.compile(r"neo4j\+s://", re.IGNORECASE),
    re.compile(r"bolt://", re.IGNORECASE),
    re.compile(r"api[_-]?key", re.IGNORECASE),
]

SAFE_FALLBACK_MESSAGE = (
    "I received your inquiry and checked your account records, but was unable to verify the "
    "generated response against our database facts. For assistance with your issue, "
    "please view your active tickets or contact our technical support team."
)


@dataclass
class ValidationResult:
    """Outcome of validating a model response."""

    is_valid: bool
    sanitized_text: str
    issues: list[str] = field(default_factory=list)
    claims_verified: bool = True


class OutputParser:
    """Validates and sanitizes AI agent outputs before presenting to users."""

    def __init__(self, max_response_chars: int = 4000) -> None:
        self.max_response_chars = max_response_chars

    def parse_and_validate(
        self,
        raw_text: str | None,
        context: CustomerMemoryContext,
        executed_tool_records: list[dict[str, Any]] | None = None,
    ) -> ValidationResult:
        """Sanitize and fact-check model response.

        Args:
            raw_text: Unprocessed string from LLM provider.
            context: Ground-truth CustomerMemoryContext retrieved from Neo4j.
            executed_tool_records: Summary of tool executions completed in this request.

        Returns:
            ValidationResult containing sanitized text or safe fallback.
        """
        issues: list[str] = []

        # 1. Empty or whitespace check
        if not raw_text or not raw_text.strip():
            logger.warning("Agent produced empty response")
            return ValidationResult(
                is_valid=False,
                sanitized_text=SAFE_FALLBACK_MESSAGE,
                issues=["empty_response"],
                claims_verified=False,
            )

        text = raw_text.strip()

        # 2. Length check
        if len(text) > self.max_response_chars:
            text = text[: self.max_response_chars].rstrip() + "... [Response truncated for length]"
            issues.append("response_truncated")

        # 3. Internal payload / secret leak detection
        for pattern in INTERNAL_LEAK_PATTERNS:
            if pattern.search(text):
                logger.warning(
                    "Detected potential internal payload or secret pattern in response: %s", pattern
                )
                issues.append("internal_payload_leak")
                return ValidationResult(
                    is_valid=False,
                    sanitized_text=SAFE_FALLBACK_MESSAGE,
                    issues=issues,
                    claims_verified=False,
                )

        # 4. Factual claim consistency checks against context and tools
        claims_ok = self._check_factual_claims(text, context, executed_tool_records or [])
        if not claims_ok:
            issues.append("unverified_factual_claim")

        return ValidationResult(
            is_valid=True,
            sanitized_text=text,
            issues=issues,
            claims_verified=claims_ok,
        )

    def _check_factual_claims(
        self,
        text: str,
        context: CustomerMemoryContext,
        executed_tools: list[dict[str, Any]],
    ) -> bool:
        """Heuristically verify that bold factual claims have backing evidence."""
        lower_text = text.lower()

        # Check for claim that ticket was created
        created_claim = any(
            phrase in lower_text
            for phrase in [
                "i have opened a ticket",
                "i created a support ticket",
                "i have created a ticket",
                "new ticket has been opened",
            ]
        )
        if created_claim:
            tool_created = any(
                t.get("tool_name") == "create_support_ticket" and t.get("success")
                for t in executed_tools
            )
            if not tool_created:
                logger.warning(
                    "Model claimed ticket was created without create_support_ticket tool execution"
                )
                return False

        # Check for claim that ticket was resolved or closed
        resolved_claim = any(
            phrase in lower_text
            for phrase in [
                "ticket has been resolved",
                "i have resolved your ticket",
                "resolved your ticket",
                "ticket is now resolved",
                "marked it resolved",
                "marked as resolved",
                "closed your ticket",
                "ticket has been closed",
            ]
        )
        if resolved_claim:
            tool_resolved = any(
                t.get("tool_name") == "update_ticket_status"
                and t.get("args", {}).get("new_status") in ("resolved", "closed")
                and t.get("success")
                for t in executed_tools
            )
            already_resolved = any(
                rt.ticket.status.value in ("resolved", "closed") for rt in context.ranked_tickets
            )
            if not tool_resolved and not already_resolved:
                logger.warning(
                    "Model claimed ticket was resolved/closed without tool or historical evidence"
                )
                return False

        return True
