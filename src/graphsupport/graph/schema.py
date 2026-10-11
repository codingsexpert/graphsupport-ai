"""Idempotent Neo4j graph schema initialization and verification.

Executes unique constraints and indexes defined for the GraphSupport AI domain model.
All statements utilize Neo4j 5.x IF NOT EXISTS semantics.
Schema operations are explicit and report statement-level diagnostic results.
"""

import logging
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

from graphsupport.core.exceptions import SchemaError

if TYPE_CHECKING:
    from neo4j import Driver

logger = logging.getLogger("graphsupport.graph.schema")

SCHEMA_STATEMENTS: list[tuple[str, str]] = [
    (
        "customer_id_unique",
        (
            "CREATE CONSTRAINT customer_id_unique IF NOT EXISTS "
            "FOR (c:Customer) REQUIRE c.id IS UNIQUE"
        ),
    ),
    (
        "customer_email_unique",
        (
            "CREATE CONSTRAINT customer_email_unique IF NOT EXISTS "
            "FOR (c:Customer) REQUIRE c.email IS UNIQUE"
        ),
    ),
    (
        "product_id_unique",
        (
            "CREATE CONSTRAINT product_id_unique IF NOT EXISTS "
            "FOR (p:Product) REQUIRE p.id IS UNIQUE"
        ),
    ),
    (
        "issue_id_unique",
        ("CREATE CONSTRAINT issue_id_unique IF NOT EXISTS FOR (i:Issue) REQUIRE i.id IS UNIQUE"),
    ),
    (
        "ticket_id_unique",
        (
            "CREATE CONSTRAINT ticket_id_unique IF NOT EXISTS "
            "FOR (t:SupportTicket) REQUIRE t.id IS UNIQUE"
        ),
    ),
    (
        "conversation_id_unique",
        (
            "CREATE CONSTRAINT conversation_id_unique IF NOT EXISTS "
            "FOR (c:Conversation) REQUIRE c.id IS UNIQUE"
        ),
    ),
    (
        "message_id_unique",
        (
            "CREATE CONSTRAINT message_id_unique IF NOT EXISTS "
            "FOR (m:Message) REQUIRE m.id IS UNIQUE"
        ),
    ),
    (
        "step_id_unique",
        (
            "CREATE CONSTRAINT step_id_unique IF NOT EXISTS "
            "FOR (s:TroubleshootingStep) REQUIRE s.id IS UNIQUE"
        ),
    ),
    (
        "resolution_id_unique",
        (
            "CREATE CONSTRAINT resolution_id_unique IF NOT EXISTS "
            "FOR (r:Resolution) REQUIRE r.id IS UNIQUE"
        ),
    ),
    (
        "ticket_status_idx",
        "CREATE INDEX ticket_status_idx IF NOT EXISTS FOR (t:SupportTicket) ON (t.status)",
    ),
    (
        "product_sku_idx",
        "CREATE INDEX product_sku_idx IF NOT EXISTS FOR (p:Product) ON (p.sku)",
    ),
]


@dataclass(frozen=True)
class StatementResult:
    """Result of executing an individual Cypher DDL statement."""

    name: str
    statement: str
    success: bool
    error: str | None = None


@dataclass(frozen=True)
class SchemaReport:
    """Consolidated summary of schema initialization execution."""

    total: int
    succeeded: int
    failed: int
    results: list[StatementResult]

    @property
    def is_successful(self) -> bool:
        """True if all statements executed without error."""
        return self.failed == 0

    def to_dict(self) -> dict[str, Any]:
        """Convert report to safe serializable dictionary."""
        return asdict(self)


def initialize_schema(driver: "Driver", database: str | None = None) -> SchemaReport:
    """Apply schema constraints and indexes to the Neo4j database idempotently.

    Args:
        driver: An active Neo4j driver instance.
        database: Target database name, or None for server default.

    Returns:
        SchemaReport detailing executed statements and outcomes.

    Raises:
        SchemaError: If critical execution failures occur during session management.
    """
    logger.info(
        "Starting idempotent schema initialization (target database: %s)...",
        database or "default",
    )
    results: list[StatementResult] = []
    succeeded = 0
    failed = 0

    try:
        with driver.session(database=database) as session:
            for name, ddl in SCHEMA_STATEMENTS:
                try:
                    session.run(ddl).consume()
                    logger.debug("Successfully verified/applied schema statement: %s", name)
                    results.append(StatementResult(name=name, statement=ddl, success=True))
                    succeeded += 1
                except Exception as err:
                    safe_err = f"{type(err).__name__}: {err}"
                    logger.warning("Schema statement '%s' encountered issue: %s", name, safe_err)
                    results.append(
                        StatementResult(name=name, statement=ddl, success=False, error=safe_err)
                    )
                    failed += 1
    except Exception as err:
        err_type = type(err).__name__
        msg = f"Failed to open database session for schema initialization: {err_type}: {err}"
        raise SchemaError(msg) from err

    report = SchemaReport(
        total=len(SCHEMA_STATEMENTS),
        succeeded=succeeded,
        failed=failed,
        results=results,
    )
    logger.info(
        "Schema initialization complete: %d/%d succeeded, %d failed",
        succeeded,
        len(SCHEMA_STATEMENTS),
        failed,
    )
    return report


def inspect_schema(driver: "Driver", database: str | None = None) -> dict[str, Any]:
    """Inspect active constraints and indexes in the Neo4j database."""
    constraints: list[str] = []
    indexes: list[str] = []

    try:
        with driver.session(database=database) as session:
            c_res = session.run("SHOW CONSTRAINTS")
            for record in c_res:
                constraints.append(str(record.get("name", "unknown")))

            i_res = session.run("SHOW INDEXES")
            for record in i_res:
                indexes.append(str(record.get("name", "unknown")))
    except Exception as err:
        logger.warning("Schema inspection query failed: %s", err)
        return {"error": str(err), "constraints": [], "indexes": []}

    return {
        "database": database or "default",
        "constraints": constraints,
        "indexes": indexes,
    }
