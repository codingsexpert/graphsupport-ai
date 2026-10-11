"""History retriever querying customer knowledge subgraphs from Neo4j (Phase 4).

Traverses customer products, open/recent tickets, tracked issues,
diagnostic attempts, resolutions, and conversations using bounded,
parameterized Cypher queries.
"""

import logging
from dataclasses import dataclass, field

from neo4j.exceptions import Neo4jError

from graphsupport.core.exceptions import (
    AuthorizationError,
    EntityNotFoundError,
    RepositoryError,
    ValidationError,
)
from graphsupport.graph.driver import Neo4jDriverManager, get_driver_manager
from graphsupport.graph.models import (
    ConversationDetails,
    Customer,
    Issue,
    Message,
    Product,
    Resolution,
    SupportTicket,
    TroubleshootingStep,
)
from graphsupport.graph.repositories.conversation_repo import ConversationRepository
from graphsupport.graph.repositories.customer_repo import CustomerRepository
from graphsupport.graph.repositories.product_repo import ProductRepository
from graphsupport.graph.repositories.ticket_repo import TicketRepository
from graphsupport.graph.repositories.troubleshooting_repo import TroubleshootingRepository
from graphsupport.memory.models import RetrievalLimits

logger = logging.getLogger("graphsupport.memory.history_retriever")


@dataclass
class RawTicketRecord:
    """Raw ticket graph record with associated nodes."""

    ticket: SupportTicket
    product: Product | None
    issue: Issue | None
    attempts: list[TroubleshootingStep] = field(default_factory=list)
    resolutions: list[Resolution] = field(default_factory=list)
    related_messages: list[Message] = field(default_factory=list)


@dataclass
class RawCustomerHistory:
    """Complete raw history extracted for a customer before ranking and bounding."""

    customer: Customer
    products: list[Product]
    ticket_records: list[RawTicketRecord]
    conversations: list[ConversationDetails]


class HistoryRetriever:
    """Retrieves relevant customer support subgraphs from Neo4j."""

    def __init__(
        self,
        driver_manager: Neo4jDriverManager | None = None,
        database: str | None = None,
    ) -> None:
        self.driver_manager = driver_manager or get_driver_manager()
        self.database = database or self.driver_manager.settings.neo4j_database

    def retrieve_raw_history(
        self,
        customer_id: str,
        product_id: str | None = None,
        ticket_id: str | None = None,
        issue_query: str | None = None,
        limits: RetrievalLimits | None = None,
    ) -> RawCustomerHistory:
        """Fetch all relevant graph records for a customer with ownership guards.

        Args:
            customer_id: Unique customer ID.
            product_id: Optional product filter.
            ticket_id: Optional ticket reference.
            issue_query: Optional search keyword or description text.
            limits: Bounding configuration limits.

        Returns:
            RawCustomerHistory populated with entities from Neo4j.

        Raises:
            ValidationError: If inputs are invalid.
            EntityNotFoundError: If customer or referenced entity does not exist.
            AuthorizationError: If ticket does not belong to the customer.
            RepositoryError: If database query execution fails.
        """
        cid = (customer_id or "").strip()
        if not cid:
            raise ValidationError("Customer ID cannot be empty")

        pid = product_id.strip() if product_id else None
        tid = ticket_id.strip() if ticket_id else None
        active_limits = limits or RetrievalLimits()

        try:
            with self.driver_manager.session(database=self.database) as session:
                # 1. Fetch Customer and verify existence
                c_record = session.run(
                    """
                    MATCH (c:Customer {id: $id})
                    RETURN c.id AS id, c.email AS email, c.name AS name, c.tier AS tier,
                           c.created_at AS created_at, c.metadata AS metadata
                    """,
                    {"id": cid},
                ).single()
                if not c_record:
                    raise EntityNotFoundError(f"Customer with ID '{cid}' does not exist")
                customer = CustomerRepository._record_to_customer(c_record)

                # 2. Ownership verification: if ticket_id provided, verify customer ownership
                if tid:
                    t_check = session.run(
                        """
                        MATCH (t:SupportTicket {id: $tid})
                        OPTIONAL MATCH (c:Customer {id: $cid})-[:HAS_TICKET]->(t)
                        RETURN count(t) > 0 AS exists, count(c) > 0 AS owned
                        """,
                        {"tid": tid, "cid": cid},
                    ).single()
                    if not (t_check and t_check["exists"]):
                        raise EntityNotFoundError(f"Ticket with ID '{tid}' does not exist")
                    if not t_check["owned"]:
                        raise AuthorizationError(
                            f"Customer '{cid}' is not authorized to access ticket '{tid}'"
                        )

                # 3. Product existence verification if provided
                if pid:
                    p_exists = bool(
                        session.run(
                            "MATCH (p:Product {id: $id}) RETURN count(p) > 0 AS ex",
                            {"id": pid},
                        ).single()["ex"]
                    )
                    if not p_exists:
                        raise EntityNotFoundError(f"Product with ID '{pid}' does not exist")

                # 4. Fetch customer products
                p_records = session.run(
                    """
                    MATCH (c:Customer {id: $cid})-[:USES]->(p:Product)
                    RETURN p.id AS id, p.name AS name, p.sku AS sku, p.category AS category,
                           p.version AS version, p.metadata AS metadata
                    ORDER BY p.name ASC, p.id ASC
                    """,
                    {"cid": cid},
                )
                products = [ProductRepository._record_to_product(r) for r in p_records]

                # 5. Fetch customer tickets with associated Product and Issue
                ticket_query = """
                MATCH (c:Customer {id: $cid})-[:HAS_TICKET]->(t:SupportTicket)
                OPTIONAL MATCH (t)-[:AFFECTS]->(p:Product)
                OPTIONAL MATCH (i:Issue)-[:TRACKED_BY]->(t)
                RETURN t.id AS id, t.title AS title, t.description AS description,
                       t.status AS status, t.priority AS priority,
                       t.created_at AS created_at, t.updated_at AS updated_at,
                       c.id AS customer_id, p.id AS product_id, i.id AS issue_id,
                       p.name AS p_name, p.sku AS p_sku, p.category AS p_cat,
                       p.version AS p_ver, p.metadata AS p_meta,
                       i.title AS i_title, i.description AS i_desc, i.category AS i_cat,
                       i.severity AS i_sev, i.created_at AS i_created
                ORDER BY t.created_at DESC, t.id ASC
                LIMIT 50
                """
                t_results = list(session.run(ticket_query, {"cid": cid}))
                raw_ticket_records: list[RawTicketRecord] = []

                for row in t_results:
                    tkt = TicketRepository._record_to_ticket(row)

                    # Build Product if present
                    prod = None
                    if row.get("product_id"):
                        prod = Product(
                            id=row["product_id"],
                            name=row.get("p_name") or "Unknown Product",
                            sku=row.get("p_sku") or "UNKNOWN",
                            category=row.get("p_cat") or "general",
                            version=row.get("p_ver") or "1.0.0",
                        )

                    # Build Issue if present
                    iss = None
                    if row.get("issue_id"):
                        iss = Issue(
                            id=row["issue_id"],
                            title=row.get("i_title") or "Unknown Issue",
                            description=row.get("i_desc") or "",
                            category=row.get("i_cat") or "general",
                            severity=row.get("i_sev") or "medium",
                            product_id=row.get("product_id"),
                        )

                    # Fetch troubleshooting attempts for ticket
                    attempts_query = """
                    MATCH (t:SupportTicket {id: $tid})-[:HAS_ATTEMPT]->(s:TroubleshootingStep)
                    OPTIONAL MATCH (prev:TroubleshootingStep)-[:FOLLOWED_BY]->(s)
                    RETURN s.id AS id, s.step_number AS step_number, s.action AS action,
                           s.outcome AS outcome, s.notes AS notes, s.executed_at AS executed_at,
                           $tid AS ticket_id, prev.id AS previous_step_id
                    ORDER BY s.step_number ASC, s.executed_at ASC, s.id ASC
                    LIMIT $max_attempts
                    """
                    att_records = session.run(
                        attempts_query,
                        {"tid": tkt.id, "max_attempts": active_limits.max_attempts_per_ticket},
                    )
                    attempts = [TroubleshootingRepository._record_to_step(r) for r in att_records]

                    # Fetch resolutions for ticket
                    res_query = """
                    MATCH (t:SupportTicket {id: $tid})-[:HAS_RESOLUTION]->(r:Resolution)
                    RETURN r.id AS id, r.summary AS summary, r.resolution_type AS resolution_type,
                           r.verified AS verified, r.created_at AS created_at, $tid AS ticket_id
                    ORDER BY r.created_at ASC, r.id ASC
                    LIMIT $max_resolutions
                    """
                    res_records = session.run(
                        res_query,
                        {
                            "tid": tkt.id,
                            "max_resolutions": active_limits.max_resolutions_per_ticket,
                        },
                    )
                    resolutions = [
                        TroubleshootingRepository._record_to_resolution(r) for r in res_records
                    ]

                    # Fetch messages explicitly linked to this ticket:
                    # (:Message)-[:ABOUT]->(:SupportTicket)
                    msg_query = """
                    MATCH (m:Message)-[:ABOUT]->(t:SupportTicket {id: $tid})
                    RETURN m.id AS id, m.sender_type AS sender_type, m.content AS content,
                           m.sequence_number AS sequence_number, m.timestamp AS timestamp,
                           $tid AS ticket_id, null AS conversation_id
                    ORDER BY m.sequence_number ASC, m.timestamp ASC
                    LIMIT 20
                    """
                    msg_records = session.run(msg_query, {"tid": tkt.id})
                    rel_messages = [
                        ConversationRepository._record_to_message(r) for r in msg_records
                    ]

                    raw_ticket_records.append(
                        RawTicketRecord(
                            ticket=tkt,
                            product=prod,
                            issue=iss,
                            attempts=attempts,
                            resolutions=resolutions,
                            related_messages=rel_messages,
                        )
                    )

                # 6. Fetch recent customer conversations and messages
                conv_query = """
                MATCH (c:Customer {id: $cid})-[:HAS_CONVERSATION]->(conv:Conversation)
                RETURN conv.id AS id, conv.session_id AS session_id, conv.channel AS channel,
                       conv.started_at AS started_at, conv.status AS status, c.id AS customer_id
                ORDER BY conv.started_at DESC, conv.id ASC
                LIMIT $max_convs
                """
                conv_rows = list(
                    session.run(
                        conv_query,
                        {"cid": cid, "max_convs": active_limits.max_conversations},
                    )
                )
                conversations: list[ConversationDetails] = []

                for crow in conv_rows:
                    conv = ConversationRepository._record_to_conversation(crow)
                    msg_list_query = """
                    MATCH (conv:Conversation {id: $conv_id})-[:CONTAINS]->(m:Message)
                    OPTIONAL MATCH (m)-[:ABOUT]->(t:SupportTicket)
                    RETURN m.id AS id, m.sender_type AS sender_type, m.content AS content,
                           m.sequence_number AS sequence_number, m.timestamp AS timestamp,
                           $conv_id AS conversation_id, t.id AS ticket_id
                    ORDER BY m.sequence_number ASC, m.timestamp ASC, m.id ASC
                    LIMIT $max_msgs
                    """
                    m_records = session.run(
                        msg_list_query,
                        {
                            "conv_id": conv.id,
                            "max_msgs": active_limits.max_messages_per_conversation,
                        },
                    )
                    c_msgs = [ConversationRepository._record_to_message(m) for m in m_records]
                    conversations.append(
                        ConversationDetails(
                            conversation=conv,
                            messages=c_msgs,
                        )
                    )

                return RawCustomerHistory(
                    customer=customer,
                    products=products,
                    ticket_records=raw_ticket_records,
                    conversations=conversations,
                )

        except (EntityNotFoundError, AuthorizationError, ValidationError):
            raise
        except Neo4jError as err:
            err_msg = getattr(err, "message", str(err))
            raise RepositoryError(
                f"Database error during history retrieval: {type(err).__name__}: {err_msg}"
            ) from err
        except Exception as err:
            raise RepositoryError(f"Unexpected failure during history retrieval: {err}") from err
