"""Graph persistence and repository layer for GraphSupport AI.

Re-exports repository classes for customer, product, ticket, conversation,
and troubleshooting persistence with managed transaction handling.
"""

from graphsupport.graph.repositories.conversation_repo import ConversationRepository
from graphsupport.graph.repositories.customer_repo import CustomerRepository
from graphsupport.graph.repositories.product_repo import ProductRepository
from graphsupport.graph.repositories.ticket_repo import TicketRepository
from graphsupport.graph.repositories.troubleshooting_repo import TroubleshootingRepository

__all__ = [
    "CustomerRepository",
    "ProductRepository",
    "TicketRepository",
    "ConversationRepository",
    "TroubleshootingRepository",
]
