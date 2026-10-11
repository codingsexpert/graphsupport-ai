"""Memory writer persisting verified support events into the knowledge graph (Phase 4).

Coordinates updates to conversation transcripts, sequential troubleshooting
attempts, and verified resolutions via the application service layer without
inventing historical facts or overwriting previous attempts.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from graphsupport.application.support_service import SupportService

from graphsupport.graph.driver import Neo4jDriverManager, get_driver_manager
from graphsupport.graph.models import (
    Message,
    Resolution,
    TroubleshootingOutcome,
    TroubleshootingStep,
)

logger = logging.getLogger("graphsupport.memory.memory_writer")


class MemoryWriter:
    """Safely updates persistent graph memory with new interactions and diagnostic evidence."""

    def __init__(
        self,
        support_service: "SupportService | None" = None,
        driver_manager: Neo4jDriverManager | None = None,
        database: str | None = None,
    ) -> None:
        if support_service:
            self.service = support_service
        else:
            from graphsupport.application.support_service import SupportService

            dm = driver_manager or get_driver_manager()
            db = database or dm.settings.neo4j_database
            self.service = SupportService(driver_manager=dm, database=db)

    def append_conversation_message(
        self,
        conversation_id: str,
        sender_type: str,
        content: str,
        ticket_id: str | None = None,
        message_id: str | None = None,
        authorized_customer_id: str | None = None,
    ) -> Message:
        """Append a validated message to persistent conversation history.

        Preserves sequence numbers and links to ticket where provided.
        """
        logger.info(
            "Writing message memory for conv=%s (sender=%s, ticket=%s)",
            conversation_id,
            sender_type,
            ticket_id,
        )
        return self.service.add_message(
            conversation_id=conversation_id,
            sender_type=sender_type,
            content=content,
            ticket_id=ticket_id,
            message_id=message_id,
            authorized_customer_id=authorized_customer_id,
        )

    def record_troubleshooting_attempt(
        self,
        ticket_id: str,
        step_number: int,
        action: str,
        outcome: TroubleshootingOutcome | str,
        notes: str = "",
        previous_step_id: str | None = None,
        step_id: str | None = None,
    ) -> TroubleshootingStep:
        """Persist a new diagnostic step without overwriting previous attempts."""
        logger.info(
            "Writing troubleshooting attempt memory for ticket=%s (step=%d, outcome=%s)",
            ticket_id,
            step_number,
            outcome,
        )
        return self.service.record_troubleshooting_step(
            ticket_id=ticket_id,
            step_number=step_number,
            action=action,
            outcome=outcome,
            notes=notes,
            previous_step_id=previous_step_id,
            step_id=step_id,
        )

    def record_verified_resolution(
        self,
        ticket_id: str,
        summary: str,
        resolution_type: str = "fix",
        verified: bool = True,
        resolution_id: str | None = None,
    ) -> Resolution:
        """Record an explicit resolution for a ticket."""
        logger.info("Writing verified resolution memory for ticket=%s", ticket_id)
        return self.service.record_ticket_resolution(
            ticket_id=ticket_id,
            summary=summary,
            resolution_type=resolution_type,
            verified=verified,
            resolution_id=resolution_id,
        )
