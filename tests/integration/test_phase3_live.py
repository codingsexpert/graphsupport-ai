"""Live integration tests for Phase 3 Customer Support Data Layer against Neo4j.

Executes end-to-end workflows across Customer, Product, Issue, Ticket,
Conversation, Message, TroubleshootingStep, and Resolution graph entities.
Uses strictly isolated test IDs ('test-phase3-<type>-<uuid>') and cleans up
all created test nodes and relationships in a guaranteed finally block.
"""

import uuid

import pytest

from graphsupport.application.support_service import SupportService
from graphsupport.config import get_settings
from graphsupport.graph.driver import Neo4jDriverManager
from graphsupport.graph.models import (
    TicketStatus,
    TroubleshootingOutcome,
)
from graphsupport.graph.repositories.conversation_repo import ConversationRepository
from graphsupport.graph.repositories.customer_repo import CustomerRepository
from graphsupport.graph.repositories.product_repo import ProductRepository
from graphsupport.graph.repositories.ticket_repo import TicketRepository
from graphsupport.graph.repositories.troubleshooting_repo import TroubleshootingRepository


def is_live_neo4j_reachable() -> bool:
    """Helper to detect if live Neo4j instance is accessible."""
    settings = get_settings()
    if not settings.is_neo4j_configured:
        return False
    try:
        manager = Neo4jDriverManager(settings=settings, connection_timeout_sec=5.0)
        return manager.verify_connectivity()
    except Exception:
        return False


live_neo4j_available = is_live_neo4j_reachable()
skip_reason = "Live Neo4j instance is unconfigured or unreachable"


@pytest.mark.skipif(not live_neo4j_available, reason=skip_reason)
def test_live_phase3_end_to_end_workflow() -> None:
    """Test full Phase 3 persistent customer support graph data layer against live Neo4j."""
    settings = get_settings()
    manager = Neo4jDriverManager(settings=settings)
    database = settings.neo4j_database

    cust_repo = CustomerRepository(driver_manager=manager, database=database)
    prod_repo = ProductRepository(driver_manager=manager, database=database)
    tkt_repo = TicketRepository(driver_manager=manager, database=database)
    conv_repo = ConversationRepository(driver_manager=manager, database=database)
    trouble_repo = TroubleshootingRepository(driver_manager=manager, database=database)

    service = SupportService(
        driver_manager=manager,
        database=database,
        customer_repo=cust_repo,
        product_repo=prod_repo,
        ticket_repo=tkt_repo,
        conversation_repo=conv_repo,
        troubleshooting_repo=trouble_repo,
    )

    # Unique test IDs
    uid = uuid.uuid4().hex[:10]
    cust_id = f"test-phase3-c-{uid}"
    cust_email = f"user-{uid}@phase3.test"
    prod_id = f"test-phase3-p-{uid}"
    prod_sku = f"SKU-P3-{uid.upper()}"
    iss_id = f"test-phase3-i-{uid}"
    tkt_id = f"test-phase3-t-{uid}"
    conv_id = f"test-phase3-conv-{uid}"
    msg1_id = f"test-phase3-m1-{uid}"
    msg2_id = f"test-phase3-m2-{uid}"
    step1_id = f"test-phase3-s1-{uid}"
    step2_id = f"test-phase3-s2-{uid}"
    res_id = f"test-phase3-r-{uid}"

    try:
        # 1. Customer registration
        customer = service.register_customer(
            email=cust_email,
            name="Phase 3 Live Test Customer",
            customer_id=cust_id,
            tier="enterprise",
        )
        assert customer.id == cust_id
        assert customer.email == cust_email

        # 2. Product registration and Customer linking
        product = service.register_or_update_product(
            name="Phase 3 Live Product Suite",
            sku=prod_sku,
            product_id=prod_id,
            category="analytics",
            version="3.0.0",
        )
        assert product.id == prod_id

        linked = service.associate_customer_with_product(cust_id, prod_id)
        assert linked is True

        cust_products = service.get_customer_products(cust_id)
        assert any(p.id == prod_id for p in cust_products)

        # 3. Known issue registration
        issue = service.record_issue(
            product_id=prod_id,
            title="Database Connection Latency Spike",
            description="Intermittent socket timeouts during peak hours",
            category="infrastructure",
            severity="high",
            issue_id=iss_id,
        )
        assert issue.id == iss_id

        # 4. Support ticket creation linked to Customer, Product, Issue
        ticket = service.open_support_ticket(
            customer_id=cust_id,
            product_id=prod_id,
            title="High Latency Report",
            description="Experiencing slow query responses in production",
            priority="high",
            issue_id=iss_id,
            ticket_id=tkt_id,
        )
        assert ticket.id == tkt_id
        assert ticket.status == TicketStatus.OPEN

        # 5. Status update
        updated_ticket = service.transition_ticket_status(tkt_id, TicketStatus.IN_PROGRESS)
        assert updated_ticket.status == TicketStatus.IN_PROGRESS

        # 6. Conversation creation
        conversation = service.start_conversation(
            customer_id=cust_id,
            channel="web",
            session_id=f"sess-{uid}",
            conversation_id=conv_id,
        )
        assert conversation.id == conv_id

        # 7. Messages with ordering and ticket link
        m1 = service.add_message(
            conversation_id=conv_id,
            sender_type="customer",
            content="Hello, our queries are running very slowly today.",
            message_id=msg1_id,
            ticket_id=tkt_id,
            authorized_customer_id=cust_id,
        )
        assert m1.id == msg1_id
        assert m1.sequence_number == 1

        m2 = service.add_message(
            conversation_id=conv_id,
            sender_type="assistant",
            content="We see the ticket and are investigating the connection pool.",
            message_id=msg2_id,
            authorized_customer_id=cust_id,
        )
        assert m2.id == msg2_id
        assert m2.sequence_number == 2

        # Verify conversation history
        conv_details = service.get_conversation_details(conv_id, authorized_customer_id=cust_id)
        assert conv_details is not None
        assert len(conv_details.messages) == 2
        assert conv_details.messages[0].sequence_number == 1
        assert conv_details.messages[1].sequence_number == 2

        # 8. Troubleshooting attempts with follow-up chaining
        step1 = service.record_troubleshooting_step(
            ticket_id=tkt_id,
            step_number=1,
            action="Inspected active connection pool counters",
            outcome=TroubleshootingOutcome.PARTIAL,
            notes="Pool max was set to default 10",
            step_id=step1_id,
        )
        assert step1.id == step1_id

        step2 = service.record_troubleshooting_step(
            ticket_id=tkt_id,
            step_number=2,
            action="Scaled pool size to 50 connections",
            outcome=TroubleshootingOutcome.SUCCESS,
            notes="Latency dropped back to 15ms",
            previous_step_id=step1_id,
            step_id=step2_id,
        )
        assert step2.id == step2_id
        assert step2.previous_step_id == step1_id

        # 9. Ticket resolution
        resolution = service.record_ticket_resolution(
            ticket_id=tkt_id,
            summary="Increased connection pool capacity to 50 connections.",
            resolution_type="fix",
            verified=True,
            resolution_id=res_id,
        )
        assert resolution.id == res_id

        # 10. Comprehensive ticket details traversal
        details = service.get_ticket_details(tkt_id)
        assert details is not None
        assert details.ticket.id == tkt_id
        assert details.customer is not None and details.customer.id == cust_id
        assert details.product is not None and details.product.id == prod_id
        assert details.issue is not None and details.issue.id == iss_id
        assert len(details.troubleshooting_steps) == 2
        assert len(details.resolutions) == 1
        assert details.resolutions[0].id == res_id

    finally:
        # Strictly isolated cleanup of all created nodes
        clean_ids = [
            ("Resolution", res_id),
            ("TroubleshootingStep", step1_id),
            ("TroubleshootingStep", step2_id),
            ("Message", msg1_id),
            ("Message", msg2_id),
            ("Conversation", conv_id),
            ("SupportTicket", tkt_id),
            ("Issue", iss_id),
            ("Product", prod_id),
            ("Customer", cust_id),
        ]
        with manager.session(database=database) as session:
            for label, entity_id in clean_ids:
                session.run(f"MATCH (n:{label} {{id: $id}}) DETACH DELETE n", {"id": entity_id})
