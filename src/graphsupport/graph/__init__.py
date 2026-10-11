"""Graph database package for GraphSupport AI."""

from graphsupport.graph.driver import (
    Neo4jDriverManager,
    close_driver_manager,
    get_driver_manager,
)
from graphsupport.graph.models import (
    Conversation,
    ConversationDetails,
    Customer,
    Issue,
    Message,
    Product,
    Resolution,
    SupportTicket,
    TicketDetails,
    TicketStatus,
    TroubleshootingOutcome,
    TroubleshootingStep,
)
from graphsupport.graph.repositories import (
    ConversationRepository,
    CustomerRepository,
    ProductRepository,
    TicketRepository,
    TroubleshootingRepository,
)
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
    "TicketDetails",
    "ConversationDetails",
    "CustomerRepository",
    "ProductRepository",
    "TicketRepository",
    "ConversationRepository",
    "TroubleshootingRepository",
    "initialize_schema",
    "inspect_schema",
    "SchemaReport",
    "StatementResult",
]
