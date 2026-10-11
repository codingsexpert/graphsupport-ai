"""Repository for TroubleshootingStep and Resolution graph entities."""

import logging
from datetime import UTC, datetime
from typing import Any

from neo4j.exceptions import ConstraintError, Neo4jError

from graphsupport.core.exceptions import EntityNotFoundError, RepositoryError
from graphsupport.graph.driver import Neo4jDriverManager, get_driver_manager
from graphsupport.graph.models import Resolution, TroubleshootingOutcome, TroubleshootingStep

logger = logging.getLogger("graphsupport.graph.repositories.troubleshooting")


class TroubleshootingRepository:
    """Repository handling TroubleshootingStep, Resolution, and [:FOLLOWED_BY] operations."""

    def __init__(
        self,
        driver_manager: Neo4jDriverManager | None = None,
        database: str | None = None,
    ) -> None:
        self.driver_manager = driver_manager or get_driver_manager()
        self.database = database or self.driver_manager.settings.neo4j_database

    def record_step(
        self,
        step: TroubleshootingStep,
        ticket_id: str,
        previous_step_id: str | None = None,
    ) -> TroubleshootingStep:
        """Persist a troubleshooting attempt, optionally chaining to predecessor."""
        logger.debug("Recording troubleshooting step %s for ticket %s...", step.id, ticket_id)
        query = """
        MATCH (t:SupportTicket {id: $ticket_id})
        MERGE (s:TroubleshootingStep {id: $id})
        ON CREATE SET
            s.step_number = $step_number,
            s.action = $action,
            s.outcome = $outcome,
            s.notes = $notes,
            s.executed_at = $executed_at
        ON MATCH SET
            s.step_number = $step_number,
            s.action = $action,
            s.outcome = $outcome,
            s.notes = $notes
        MERGE (t)-[:HAS_ATTEMPT]->(s)
        WITH s, t
        CALL {
            WITH s, t
            WITH s, t WHERE $previous_step_id IS NOT NULL
            MATCH (t)-[:HAS_ATTEMPT]->(prev:TroubleshootingStep {id: $previous_step_id})
            MERGE (prev)-[:FOLLOWED_BY]->(s)
            RETURN count(prev) AS linked_followup
        }
        RETURN s.id AS id, s.step_number AS step_number, s.action AS action,
               s.outcome AS outcome, s.notes AS notes, s.executed_at AS executed_at,
               $ticket_id AS ticket_id, $previous_step_id AS previous_step_id
        """
        params = {
            "id": step.id,
            "step_number": step.step_number,
            "action": step.action,
            "outcome": step.outcome.value,
            "notes": step.notes,
            "executed_at": step.executed_at.isoformat(),
            "ticket_id": ticket_id,
            "previous_step_id": previous_step_id,
        }
        try:
            with self.driver_manager.session(database=self.database) as session:
                t_check = session.run(
                    "MATCH (t:SupportTicket {id: $id}) RETURN count(t) > 0 AS ex", {"id": ticket_id}
                ).single()
                if not (t_check and t_check["ex"]):
                    raise EntityNotFoundError(f"Ticket with ID '{ticket_id}' does not exist")

                if previous_step_id:
                    check_q = (
                        "MATCH (t:SupportTicket {id: $ticket_id})"
                        "-[:HAS_ATTEMPT]->(prev:TroubleshootingStep {id: $prev_id}) "
                        "RETURN count(prev) > 0 AS ex"
                    )
                    p_check = session.run(
                        check_q,
                        {"ticket_id": ticket_id, "prev_id": previous_step_id},
                    ).single()
                    if not (p_check and p_check["ex"]):
                        raise EntityNotFoundError(
                            f"Previous step '{previous_step_id}' does not exist "
                            f"on ticket '{ticket_id}'"
                        )

                record = session.run(query, params).single()
                if not record:
                    raise RepositoryError("Failed to record troubleshooting step")
                return self._record_to_step(record)
        except EntityNotFoundError:
            raise
        except ConstraintError as err:
            err_msg = getattr(err, "message", str(err))
            raise RepositoryError(f"Troubleshooting step constraint violation: {err_msg}") from err
        except Neo4jError as err:
            raise RepositoryError(f"Database error recording step: {err.message}") from err
        except Exception as err:
            raise RepositoryError(f"Failed to record step: {err}") from err

    def get_ticket_attempts(self, ticket_id: str) -> list[TroubleshootingStep]:
        """Retrieve all troubleshooting attempts for a ticket in chronological order."""
        query = """
        MATCH (t:SupportTicket {id: $ticket_id})-[:HAS_ATTEMPT]->(s:TroubleshootingStep)
        OPTIONAL MATCH (prev:TroubleshootingStep)-[:FOLLOWED_BY]->(s)
        RETURN s.id AS id, s.step_number AS step_number, s.action AS action,
               s.outcome AS outcome, s.notes AS notes, s.executed_at AS executed_at,
               $ticket_id AS ticket_id, prev.id AS previous_step_id
        ORDER BY s.step_number ASC, s.executed_at ASC, s.id ASC
        """
        steps: list[TroubleshootingStep] = []
        try:
            with self.driver_manager.session(database=self.database) as session:
                result = session.run(query, {"ticket_id": ticket_id})
                for record in result:
                    steps.append(self._record_to_step(record))
            return steps
        except Exception as err:
            raise RepositoryError(
                f"Failed to fetch ticket troubleshooting attempts: {err}"
            ) from err

    def record_resolution(self, resolution: Resolution, ticket_id: str) -> Resolution:
        """Persist a resolution linked to a support ticket via [:HAS_RESOLUTION]."""
        logger.debug("Recording resolution %s for ticket %s...", resolution.id, ticket_id)
        query = """
        MATCH (t:SupportTicket {id: $ticket_id})
        MERGE (r:Resolution {id: $id})
        ON CREATE SET
            r.summary = $summary,
            r.resolution_type = $resolution_type,
            r.verified = $verified,
            r.created_at = $created_at
        ON MATCH SET
            r.summary = $summary,
            r.resolution_type = $resolution_type,
            r.verified = $verified
        MERGE (t)-[:HAS_RESOLUTION]->(r)
        RETURN r.id AS id, r.summary AS summary, r.resolution_type AS resolution_type,
               r.verified AS verified, r.created_at AS created_at, $ticket_id AS ticket_id
        """
        params = {
            "id": resolution.id,
            "summary": resolution.summary,
            "resolution_type": resolution.resolution_type,
            "verified": resolution.verified,
            "created_at": resolution.created_at.isoformat(),
            "ticket_id": ticket_id,
        }
        try:
            with self.driver_manager.session(database=self.database) as session:
                t_check = session.run(
                    "MATCH (t:SupportTicket {id: $id}) RETURN count(t) > 0 AS ex", {"id": ticket_id}
                ).single()
                if not (t_check and t_check["ex"]):
                    raise EntityNotFoundError(f"Ticket with ID '{ticket_id}' does not exist")

                record = session.run(query, params).single()
                if not record:
                    raise RepositoryError("Failed to record resolution")
                return self._record_to_resolution(record)
        except EntityNotFoundError:
            raise
        except ConstraintError as err:
            raise RepositoryError(f"Resolution constraint violation: {err.message}") from err
        except Neo4jError as err:
            raise RepositoryError(f"Database error recording resolution: {err.message}") from err
        except Exception as err:
            raise RepositoryError(f"Failed to record resolution: {err}") from err

    def get_ticket_resolutions(self, ticket_id: str) -> list[Resolution]:
        """Retrieve all recorded resolutions for a ticket."""
        query = """
        MATCH (t:SupportTicket {id: $ticket_id})-[:HAS_RESOLUTION]->(r:Resolution)
        RETURN r.id AS id, r.summary AS summary, r.resolution_type AS resolution_type,
               r.verified AS verified, r.created_at AS created_at, $ticket_id AS ticket_id
        ORDER BY r.created_at ASC, r.id ASC
        """
        resolutions: list[Resolution] = []
        try:
            with self.driver_manager.session(database=self.database) as session:
                result = session.run(query, {"ticket_id": ticket_id})
                for record in result:
                    resolutions.append(self._record_to_resolution(record))
            return resolutions
        except Exception as err:
            raise RepositoryError(f"Failed to fetch ticket resolutions: {err}") from err

    def delete_step_by_id(self, step_id: str) -> bool:
        """Delete a troubleshooting step (used for cleanup)."""
        query = "MATCH (s:TroubleshootingStep {id: $id}) DETACH DELETE s RETURN count(s) AS c"
        try:
            with self.driver_manager.session(database=self.database) as session:
                result = session.run(query, {"id": step_id}).single()
                return bool(result and result["c"] > 0)
        except Exception as err:
            raise RepositoryError(f"Failed to delete step: {err}") from err

    def delete_resolution_by_id(self, resolution_id: str) -> bool:
        """Delete a resolution (used for cleanup)."""
        query = "MATCH (r:Resolution {id: $id}) DETACH DELETE r RETURN count(r) AS c"
        try:
            with self.driver_manager.session(database=self.database) as session:
                result = session.run(query, {"id": resolution_id}).single()
                return bool(result and result["c"] > 0)
        except Exception as err:
            raise RepositoryError(f"Failed to delete resolution: {err}") from err

    def list_recent_steps(self, limit: int = 10) -> list[TroubleshootingStep]:
        """List recent troubleshooting steps across tickets."""
        query = """
        MATCH (t:SupportTicket)-[:HAS_ATTEMPT]->(s:TroubleshootingStep)
        RETURN s.id AS id, s.step_number AS step_number, s.action AS action,
               s.outcome AS outcome, s.notes AS notes, s.executed_at AS executed_at,
               t.id AS ticket_id, s.previous_step_id AS previous_step_id
        ORDER BY s.executed_at DESC, s.id ASC
        LIMIT $limit
        """
        steps: list[TroubleshootingStep] = []
        try:
            with self.driver_manager.session(database=self.database) as session:
                result = session.run(query, {"limit": limit})
                for record in result:
                    steps.append(self._record_to_step(record))
            return steps
        except Exception as err:
            raise RepositoryError(f"Failed to list recent steps: {err}") from err

    def list_recent_resolutions(self, limit: int = 10) -> list[Resolution]:
        """List recent verified resolutions across tickets."""
        query = """
        MATCH (t:SupportTicket)-[:HAS_RESOLUTION]->(r:Resolution)
        RETURN r.id AS id, r.summary AS summary, r.resolution_type AS resolution_type,
               r.verified AS verified, r.created_at AS created_at, t.id AS ticket_id
        ORDER BY r.created_at DESC, r.id ASC
        LIMIT $limit
        """
        resolutions: list[Resolution] = []
        try:
            with self.driver_manager.session(database=self.database) as session:
                result = session.run(query, {"limit": limit})
                for record in result:
                    resolutions.append(self._record_to_resolution(record))
            return resolutions
        except Exception as err:
            raise RepositoryError(f"Failed to list recent resolutions: {err}") from err

    @staticmethod
    def _record_to_step(record: Any) -> TroubleshootingStep:
        executed_at_raw = record.get("executed_at")
        executed_at = (
            datetime.fromisoformat(executed_at_raw)
            if isinstance(executed_at_raw, str)
            else (executed_at_raw or datetime.now(UTC))
        )
        return TroubleshootingStep(
            id=record["id"],
            ticket_id=record.get("ticket_id"),
            step_number=record["step_number"],
            action=record["action"],
            outcome=TroubleshootingOutcome(record["outcome"]),
            notes=record.get("notes"),
            executed_at=executed_at,
            previous_step_id=record.get("previous_step_id"),
        )

    @staticmethod
    def _record_to_resolution(record: Any) -> Resolution:
        created_at_raw = record.get("created_at")
        created_at = (
            datetime.fromisoformat(created_at_raw)
            if isinstance(created_at_raw, str)
            else (created_at_raw or datetime.now(UTC))
        )
        return Resolution(
            id=record["id"],
            ticket_id=record.get("ticket_id"),
            summary=record["summary"],
            resolution_type=record.get("resolution_type", "workaround"),
            verified=bool(record.get("verified", True)),
            created_at=created_at,
        )
