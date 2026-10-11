"""Graph database package for GraphSupport AI."""

from graphsupport.graph.driver import (
    Neo4jDriverManager,
    close_driver_manager,
    get_driver_manager,
)
from graphsupport.graph.models import (
    Conversation,
    Customer,
    Issue,
    Message,
    Product,
    Resolution,
    SupportTicket,
    TicketStatus,
    TroubleshootingOutcome,
    TroubleshootingStep,
)
from graphsupport.graph.repository import CustomerRepository
from graphsupport.graph.schema import (
    SchemaReport,
    StatementResult,
    initialize_schema,
    inspect_schema,
)

__all__ = [
    "Neo4jDriverManager",
    "get_driver_manager",
    "close_driver_manager",
    "Customer",
    "Product",
    "Issue",
    "SupportTicket",
    "Conversation",
    "Message",
    "TroubleshootingStep",
    "Resolution",
    "TicketStatus",
    "TroubleshootingOutcome",
    "CustomerRepository",
    "initialize_schema",
    "inspect_schema",
    "SchemaReport",
    "StatementResult",
]
