"""Repository for SupportTicket, Issue entities, and ticket graph relationships."""

import logging
from datetime import UTC, datetime
from typing import Any

from neo4j.exceptions import ConstraintError, Neo4jError

from graphsupport.core.exceptions import EntityNotFoundError, RepositoryError, ValidationError
from graphsupport.graph.driver import Neo4jDriverManager, get_driver_manager
from graphsupport.graph.models import (
    Issue,
    Resolution,
    SupportTicket,
    TicketDetails,
    TicketStatus,
    TroubleshootingOutcome,
    TroubleshootingStep,
)

logger = logging.getLogger("graphsupport.graph.repositories.ticket")


class TicketRepository:
    """Repository handling (:SupportTicket) and (:Issue) persistence and status updates."""

    def __init__(
        self,
        driver_manager: Neo4jDriverManager | None = None,
        database: str | None = None,
    ) -> None:
        self.driver_manager = driver_manager or get_driver_manager()
        self.database = database or self.driver_manager.settings.neo4j_database

    def create_issue(self, issue: Issue, product_id: str) -> Issue:
        """Create an Issue node and link to Product via (:Product)-[:HAS_ISSUE]->(:Issue)."""
        logger.debug("Creating issue '%s' for product %s...", issue.title, product_id)
        query = """
        MATCH (p:Product {id: $product_id})
        CREATE (i:Issue {
            id: $id,
            title: $title,
            description: $description,
            category: $category,
            severity: $severity,
            created_at: $created_at
        })
        MERGE (p)-[:HAS_ISSUE]->(i)
        RETURN i.id AS id, i.title AS title, i.description AS description,
               i.category AS category, i.severity AS severity, i.created_at AS created_at,
               p.id AS product_id
        """
        params = {
            "id": issue.id,
            "title": issue.title,
            "description": issue.description,
            "category": issue.category,
            "severity": issue.severity,
            "created_at": issue.created_at.isoformat(),
            "product_id": product_id,
        }
        try:
            with self.driver_manager.session(database=self.database) as session:
                record = session.run(query, params).single()
                if not record:
                    p_exists = session.run(
                        "MATCH (p:Product {id: $id}) RETURN count(p) > 0 AS ex", {"id": product_id}
                    ).single()
                    if not (p_exists and p_exists["ex"]):
                        raise EntityNotFoundError(f"Product with ID '{product_id}' does not exist")
                    raise RepositoryError(f"Failed to create issue for product {product_id}")
                return self._record_to_issue(record)
        except EntityNotFoundError:
            raise
        except ConstraintError as err:
            raise RepositoryError(f"Issue constraint violation: {err.message}") from err
        except Neo4jError as err:
            raise RepositoryError(f"Database error during issue creation: {err.message}") from err
        except Exception as err:
            raise RepositoryError(f"Failed to create issue: {err}") from err

    def get_issue_by_id(self, issue_id: str) -> Issue | None:
        """Retrieve an Issue entity by ID."""
        query = """
        MATCH (i:Issue {id: $id})
        OPTIONAL MATCH (p:Product)-[:HAS_ISSUE]->(i)
        RETURN i.id AS id, i.title AS title, i.description AS description,
               i.category AS category, i.severity AS severity, i.created_at AS created_at,
               p.id AS product_id
        """
        try:
            with self.driver_manager.session(database=self.database) as session:
                record = session.run(query, {"id": issue_id}).single()
                if not record:
                    return None
                return self._record_to_issue(record)
        except Exception as err:
            raise RepositoryError(f"Failed to retrieve issue by ID: {err}") from err

    def create_ticket(
        self,
        ticket: SupportTicket,
        customer_id: str,
        product_id: str,
        issue_id: str | None = None,
    ) -> SupportTicket:
        """Create a SupportTicket atomically linked to Customer, Product, and optional Issue."""
        logger.debug(
            "Creating ticket '%s' for customer %s and product %s...",
            ticket.title,
            customer_id,
            product_id,
        )
        query = """
        MATCH (c:Customer {id: $customer_id})
        MATCH (p:Product {id: $product_id})
        CREATE (t:SupportTicket {
            id: $id,
            title: $title,
            description: $description,
            status: $status,
            priority: $priority,
            created_at: $created_at,
            updated_at: $updated_at
        })
        MERGE (c)-[:HAS_TICKET]->(t)
        MERGE (t)-[:AFFECTS]->(p)
        WITH t, c, p
        CALL {
            WITH t
            WITH t WHERE $issue_id IS NOT NULL
            MATCH (i:Issue {id: $issue_id})
            MERGE (i)-[:TRACKED_BY]->(t)
            RETURN count(i) AS linked_issue
        }
        RETURN t.id AS id, t.title AS title, t.description AS description,
               t.status AS status, t.priority AS priority,
               t.created_at AS created_at, t.updated_at AS updated_at,
               c.id AS customer_id, p.id AS product_id, $issue_id AS issue_id
        """
        params = {
            "id": ticket.id,
            "title": ticket.title,
            "description": ticket.description,
            "status": ticket.status.value,
            "priority": ticket.priority,
            "created_at": ticket.created_at.isoformat(),
            "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
            "customer_id": customer_id,
            "product_id": product_id,
            "issue_id": issue_id,
        }
        try:
            with self.driver_manager.session(database=self.database) as session:
                record = session.run(query, params).single()
                if not record:
                    # Validate which reference was missing
                    c_exists = bool(
                        session.run(
                            "MATCH (c:Customer {id: $id}) RETURN count(c) > 0 AS ex",
                            {"id": customer_id},
                        ).single()["ex"]
                    )
                    if not c_exists:
                        raise EntityNotFoundError(
                            f"Customer with ID '{customer_id}' does not exist"
                        )

                    p_exists = bool(
                        session.run(
                            "MATCH (p:Product {id: $id}) RETURN count(p) > 0 AS ex",
                            {"id": product_id},
                        ).single()["ex"]
                    )
                    if not p_exists:
                        raise EntityNotFoundError(f"Product with ID '{product_id}' does not exist")

                    if issue_id:
                        i_exists = bool(
                            session.run(
                                "MATCH (i:Issue {id: $id}) RETURN count(i) > 0 AS ex",
                                {"id": issue_id},
                            ).single()["ex"]
                        )
                        if not i_exists:
                            raise EntityNotFoundError(f"Issue with ID '{issue_id}' does not exist")

                    raise RepositoryError("Failed to create ticket: unexpected link failure")

                return self._record_to_ticket(record)
        except EntityNotFoundError:
            raise
        except ConstraintError as err:
            raise RepositoryError(f"Ticket constraint violation: {err.message}") from err
        except Neo4jError as err:
            raise RepositoryError(f"Database error during ticket creation: {err.message}") from err
        except Exception as err:
            raise RepositoryError(f"Failed to create support ticket: {err}") from err

    def get_by_id(self, ticket_id: str) -> SupportTicket | None:
        """Retrieve a SupportTicket by ID."""
        query = """
        MATCH (t:SupportTicket {id: $id})
        OPTIONAL MATCH (c:Customer)-[:HAS_TICKET]->(t)
        OPTIONAL MATCH (t)-[:AFFECTS]->(p:Product)
        OPTIONAL MATCH (i:Issue)-[:TRACKED_BY]->(t)
        RETURN t.id AS id, t.title AS title, t.description AS description,
               t.status AS status, t.priority AS priority,
               t.created_at AS created_at, t.updated_at AS updated_at,
               c.id AS customer_id, p.id AS product_id, i.id AS issue_id
        """
        try:
            with self.driver_manager.session(database=self.database) as session:
                record = session.run(query, {"id": ticket_id}).single()
                if not record:
                    return None
                return self._record_to_ticket(record)
        except Exception as err:
            raise RepositoryError(f"Failed to retrieve ticket by ID: {err}") from err

    def update_ticket_status(self, ticket_id: str, new_status: TicketStatus) -> SupportTicket:
        """Update ticket workflow status and record updated_at timestamp."""
        now_iso = datetime.now(UTC).isoformat()
        query = """
        MATCH (t:SupportTicket {id: $id})
        SET t.status = $status, t.updated_at = $updated_at
        WITH t
        OPTIONAL MATCH (c:Customer)-[:HAS_TICKET]->(t)
        OPTIONAL MATCH (t)-[:AFFECTS]->(p:Product)
        OPTIONAL MATCH (i:Issue)-[:TRACKED_BY]->(t)
        RETURN t.id AS id, t.title AS title, t.description AS description,
               t.status AS status, t.priority AS priority,
               t.created_at AS created_at, t.updated_at AS updated_at,
               c.id AS customer_id, p.id AS product_id, i.id AS issue_id
        """
        params = {
            "id": ticket_id,
            "status": new_status.value,
            "updated_at": now_iso,
        }
        try:
            with self.driver_manager.session(database=self.database) as session:
                record = session.run(query, params).single()
                if not record:
                    raise EntityNotFoundError(f"Ticket with ID '{ticket_id}' does not exist")
                return self._record_to_ticket(record)
        except EntityNotFoundError:
            raise
        except Exception as err:
            raise RepositoryError(f"Failed to update ticket status: {err}") from err

    def list_customer_tickets(
        self,
        customer_id: str,
        status: TicketStatus | None = None,
        limit: int = 50,
        skip: int = 0,
    ) -> list[SupportTicket]:
        """List tickets belonging to a customer with optional status filtering and pagination."""
        if limit < 1 or limit > 500:
            raise ValidationError(f"Limit must be between 1 and 500, got {limit}")
        if skip < 0:
            raise ValidationError(f"Skip cannot be negative, got {skip}")

        query = """
        MATCH (c:Customer {id: $customer_id})-[:HAS_TICKET]->(t:SupportTicket)
        WHERE ($status IS NULL OR t.status = $status)
        OPTIONAL MATCH (t)-[:AFFECTS]->(p:Product)
        OPTIONAL MATCH (i:Issue)-[:TRACKED_BY]->(t)
        RETURN t.id AS id, t.title AS title, t.description AS description,
               t.status AS status, t.priority AS priority,
               t.created_at AS created_at, t.updated_at AS updated_at,
               c.id AS customer_id, p.id AS product_id, i.id AS issue_id
        ORDER BY t.created_at DESC, t.id ASC
        SKIP $skip
        LIMIT $limit
        """
        params = {
            "customer_id": customer_id,
            "status": status.value if status else None,
            "skip": skip,
            "limit": limit,
        }
        tickets: list[SupportTicket] = []
        try:
            with self.driver_manager.session(database=self.database) as session:
                result = session.run(query, params)
                for record in result:
                    tickets.append(self._record_to_ticket(record))
            return tickets
        except Exception as err:
            raise RepositoryError(f"Failed to list customer tickets: {err}") from err

    def list_all_tickets(
        self,
        status: TicketStatus | None = None,
        limit: int = 50,
        skip: int = 0,
    ) -> list[SupportTicket]:
        """List all tickets across customers with optional status filtering and pagination."""
        if limit < 1 or limit > 500:
            raise ValidationError(f"Limit must be between 1 and 500, got {limit}")
        if skip < 0:
            raise ValidationError(f"Skip cannot be negative, got {skip}")

        query = """
        MATCH (t:SupportTicket)
        WHERE ($status IS NULL OR t.status = $status)
        OPTIONAL MATCH (c:Customer)-[:HAS_TICKET]->(t)
        OPTIONAL MATCH (t)-[:AFFECTS]->(p:Product)
        OPTIONAL MATCH (i:Issue)-[:TRACKED_BY]->(t)
        RETURN t.id AS id, t.title AS title, t.description AS description,
               t.status AS status, t.priority AS priority,
               t.created_at AS created_at, t.updated_at AS updated_at,
               c.id AS customer_id, p.id AS product_id, i.id AS issue_id
        ORDER BY t.created_at DESC, t.id ASC
        SKIP $skip
        LIMIT $limit
        """
        params = {
            "status": status.value if status else None,
            "skip": skip,
            "limit": limit,
        }
        tickets: list[SupportTicket] = []
        try:
            with self.driver_manager.session(database=self.database) as session:
                result = session.run(query, params)
                for record in result:
                    tickets.append(self._record_to_ticket(record))
            return tickets
        except Exception as err:
            raise RepositoryError(f"Failed to list all tickets: {err}") from err

    def get_ticket_details(self, ticket_id: str) -> TicketDetails | None:
        """Fetch comprehensive ticket graph context including steps and resolutions."""
        ticket = self.get_by_id(ticket_id)
        if not ticket:
            return None

        # Fetch Customer
        customer = None
        if ticket.customer_id:
            from graphsupport.graph.repositories.customer_repo import CustomerRepository

            c_repo = CustomerRepository(driver_manager=self.driver_manager, database=self.database)
            customer = c_repo.get_by_id(ticket.customer_id)

        # Fetch Product
        product = None
        if ticket.product_id:
            from graphsupport.graph.repositories.product_repo import ProductRepository

            p_repo = ProductRepository(driver_manager=self.driver_manager, database=self.database)
            product = p_repo.get_by_id(ticket.product_id)

        # Fetch Issue
        issue = None
        if ticket.issue_id:
            issue = self.get_issue_by_id(ticket.issue_id)

        # Fetch Troubleshooting steps
        steps_query = """
        MATCH (t:SupportTicket {id: $id})-[:HAS_ATTEMPT]->(s:TroubleshootingStep)
        RETURN s.id AS id, s.step_number AS step_number, s.action AS action,
               s.outcome AS outcome, s.notes AS notes, s.executed_at AS executed_at,
               $id AS ticket_id
        ORDER BY s.step_number ASC, s.executed_at ASC
        """
        steps: list[TroubleshootingStep] = []

        # Fetch Resolutions
        resolutions_query = """
        MATCH (t:SupportTicket {id: $id})-[:HAS_RESOLUTION]->(r:Resolution)
        RETURN r.id AS id, r.summary AS summary, r.resolution_type AS resolution_type,
               r.verified AS verified, r.created_at AS created_at, $id AS ticket_id
        ORDER BY r.created_at ASC
        """
        resolutions: list[Resolution] = []

        try:
            with self.driver_manager.session(database=self.database) as session:
                for r in session.run(steps_query, {"id": ticket_id}):
                    steps.append(
                        TroubleshootingStep(
                            id=r["id"],
                            ticket_id=ticket_id,
                            step_number=r["step_number"],
                            action=r["action"],
                            outcome=TroubleshootingOutcome(r["outcome"]),
                            notes=r.get("notes"),
                            executed_at=datetime.fromisoformat(r["executed_at"]),
                        )
                    )

                for r in session.run(resolutions_query, {"id": ticket_id}):
                    resolutions.append(
                        Resolution(
                            id=r["id"],
                            ticket_id=ticket_id,
                            summary=r["summary"],
                            resolution_type=r["resolution_type"],
                            verified=bool(r["verified"]),
                            created_at=datetime.fromisoformat(r["created_at"]),
                        )
                    )
        except Exception as err:
            logger.warning("Error fetching sub-graph elements for ticket %s: %s", ticket_id, err)

        return TicketDetails(
            ticket=ticket,
            customer=customer,
            product=product,
            issue=issue,
            troubleshooting_steps=steps,
            resolutions=resolutions,
        )

    def delete_by_id(self, ticket_id: str) -> bool:
        """Delete ticket by ID (used for test data cleanup)."""
        query = """
        MATCH (t:SupportTicket {id: $id})
        DETACH DELETE t
        RETURN count(t) AS deleted_count
        """
        try:
            with self.driver_manager.session(database=self.database) as session:
                result = session.run(query, {"id": ticket_id}).single()
                return bool(result and result["deleted_count"] > 0)
        except Exception as err:
            raise RepositoryError(f"Failed to delete ticket {ticket_id}: {err}") from err

    @staticmethod
    def _record_to_ticket(record: Any) -> SupportTicket:
        created_at_raw = record.get("created_at")
        created_at = (
            datetime.fromisoformat(created_at_raw)
            if isinstance(created_at_raw, str)
            else (created_at_raw or datetime.now(UTC))
        )

        updated_at_raw = record.get("updated_at")
        updated_at = (
            datetime.fromisoformat(updated_at_raw)
            if isinstance(updated_at_raw, str)
            else updated_at_raw
        )

        return SupportTicket(
            id=record["id"],
            title=record["title"],
            description=record.get("description", ""),
            status=TicketStatus(record["status"]),
            priority=record.get("priority", "normal"),
            customer_id=record.get("customer_id"),
            product_id=record.get("product_id"),
            issue_id=record.get("issue_id"),
            created_at=created_at,
            updated_at=updated_at,
        )

    @staticmethod
    def _record_to_issue(record: Any) -> Issue:
        created_at_raw = record.get("created_at")
        created_at = (
            datetime.fromisoformat(created_at_raw)
            if isinstance(created_at_raw, str)
            else (created_at_raw or datetime.now(UTC))
        )
        return Issue(
            id=record["id"],
            title=record["title"],
            description=record.get("description", ""),
            category=record.get("category", "general"),
            severity=record.get("severity", "medium"),
            product_id=record.get("product_id"),
            created_at=created_at,
        )
