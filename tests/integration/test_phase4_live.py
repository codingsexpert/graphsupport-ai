"""Live integration tests for Phase 4 Persistent Graph Memory & Context Retrieval.

Validates end-to-end memory retrieval against live Neo4j:
- Historical context retrieval across separate application sessions.
- Troubleshooting outcome fidelity (failed attempt remains strictly failed).
- Tenant/customer isolation (Customer B cannot retrieve or see Customer A's tickets).
- Bounded, serializable memory context generation with explainable ranking.
All test entities use unique isolated IDs ('test-phase4-<type>-<uuid>') and
are cleaned up in a guaranteed finally block. Never drops or affects production data.
"""

import uuid

import pytest

from graphsupport.application.support_service import SupportService
from graphsupport.config import get_settings
from graphsupport.core.exceptions import AuthorizationError
from graphsupport.graph.driver import Neo4jDriverManager
from graphsupport.graph.models import (
    TicketStatus,
    TroubleshootingOutcome,
)
from graphsupport.memory.models import CustomerMemoryContext, RetrievalLimits


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
def test_live_phase4_cross_session_memory_persistence() -> None:
    """Test full Phase 4 persistent graph memory lifecycle and session boundary crossing."""
    settings = get_settings()
    manager = Neo4jDriverManager(settings=settings)
    database = settings.neo4j_database

    session_id = uuid.uuid4().hex[:8]
    cust1_id = f"test-phase4-cust1-{session_id}"
    cust2_id = f"test-phase4-cust2-{session_id}"
    prod_id = f"test-phase4-prod-{session_id}"
    iss_id = f"test-phase4-iss-{session_id}"
    tkt_id = f"test-phase4-tkt-{session_id}"
    step1_id = f"test-phase4-step1-{session_id}"
    res_id = f"test-phase4-res-{session_id}"
    conv_id = f"test-phase4-conv-{session_id}"
    msg_id = f"test-phase4-msg-{session_id}"

    # Session 1: Create initial state
    service_session_1 = SupportService(driver_manager=manager, database=database)

    try:
        # 1. Register two isolated test customers
        cust1 = service_session_1.register_customer(
            customer_id=cust1_id,
            email=f"alpha_{session_id}@example.com",
            name="Alpha Customer",
            tier="pro",
        )
        assert cust1.id == cust1_id

        cust2 = service_session_1.register_customer(
            customer_id=cust2_id,
            email=f"beta_{session_id}@example.com",
            name="Beta Customer",
            tier="standard",
        )
        assert cust2.id == cust2_id

        # 2. Register product & associate with Customer 1
        product = service_session_1.register_or_update_product(
            product_id=prod_id,
            sku=f"SKU-{session_id}",
            name="Smart Gateway Pro",
            category="Hardware",
        )
        assert product.id == prod_id
        service_session_1.associate_customer_with_product(customer_id=cust1_id, product_id=prod_id)

        # 3. Create issue & support ticket for Customer 1
        issue = service_session_1.record_issue(
            issue_id=iss_id,
            product_id=prod_id,
            title="Gateway boot loop",
            description="Gateway restarts after flashing LED",
            category="firmware",
            severity="high",
        )
        assert issue.id == iss_id

        ticket = service_session_1.open_support_ticket(
            ticket_id=tkt_id,
            customer_id=cust1_id,
            product_id=prod_id,
            issue_id=iss_id,
            title="Gateway keeps rebooting",
            description="Flashing red light then power cycles",
            priority="urgent",
        )
        assert ticket.id == tkt_id

        # 4. Record a failed troubleshooting step
        failed_step = service_session_1.record_troubleshooting_step(
            ticket_id=tkt_id,
            step_number=1,
            action="Hold reset pin for 30s to trigger factory reset",
            outcome=TroubleshootingOutcome.FAILED,
            notes="Device still reboots after factory reset attempt",
            step_id=step1_id,
        )
        assert failed_step.id == step1_id
        assert failed_step.outcome == TroubleshootingOutcome.FAILED

        # 5. Add a conversation message
        conv = service_session_1.start_conversation(
            customer_id=cust1_id,
            channel="web_portal",
            conversation_id=conv_id,
        )
        service_session_1.add_message(
            conversation_id=conv.id,
            sender_type="customer",
            content="I tried resetting it but it did not work.",
            ticket_id=tkt_id,
            message_id=msg_id,
            authorized_customer_id=cust1_id,
        )

        # =====================================================================
        # SESSION BOUNDARY: Close Session 1 and instantiate completely fresh
        # SupportService instance representing a new user session or turn.
        # =====================================================================
        del service_session_1

        service_session_2 = SupportService(driver_manager=manager, database=database)

        # 6. Retrieve customer 1 memory context from Neo4j in the new session
        context1: CustomerMemoryContext = service_session_2.retrieve_customer_context(
            customer_id=cust1_id,
            issue_query="gateway reboot bootloop",
            limits=RetrievalLimits(max_tickets=5),
        )

        assert context1.customer.id == cust1_id
        assert len(context1.products) >= 1
        assert any(p.id == prod_id for p in context1.products)
        assert len(context1.ranked_tickets) == 1

        top_ticket_ctx = context1.ranked_tickets[0]
        assert top_ticket_ctx.ticket.id == tkt_id
        assert top_ticket_ctx.ticket.status == TicketStatus.OPEN

        # Verify outcome fidelity across session: failed step remains strictly failed
        assert len(top_ticket_ctx.troubleshooting_attempts) == 1
        retrieved_attempt = top_ticket_ctx.troubleshooting_attempts[0]
        assert retrieved_attempt.id == step1_id
        assert retrieved_attempt.outcome == TroubleshootingOutcome.FAILED
        assert "Device still reboots" in retrieved_attempt.notes

        # Verify explainable ranking factors
        assert top_ticket_ctx.relevance_score > 0
        ranking_str = " ".join(top_ticket_ctx.ranking_reasons)
        assert "status_open" in ranking_str
        assert "has_failed_attempts" in ranking_str

        # Verify missing information indicators
        assert any("has_failed_attempt_step_1" in flag for flag in context1.missing_information)

        # 7. Verify serialization
        summary = context1.to_summary_dict()
        assert summary["customer_id"] == cust1_id
        assert summary["ranked_tickets_count"] == 1

        full_dict = context1.to_dict()
        assert full_dict["customer"]["id"] == cust1_id

        # 8. Authorization boundary check: Customer 2 must NOT access Customer 1's ticket
        with pytest.raises(AuthorizationError, match="is not authorized to access ticket"):
            service_session_2.retrieve_customer_context(
                customer_id=cust2_id,
                ticket_id=tkt_id,  # belongs to cust1
            )

        # 9. Verify Customer 2 context is empty and isolated
        context2 = service_session_2.retrieve_customer_context(customer_id=cust2_id)
        assert context2.customer.id == cust2_id
        assert len(context2.ranked_tickets) == 0
        assert "no_support_tickets_found" in context2.missing_information

        # 10. Record verified resolution in Session 2 and verify updated context
        res = service_session_2.record_ticket_resolution(
            ticket_id=tkt_id,
            summary="Replaced corrupted flash firmware chip via warranty RMA.",
            resolution_type="replacement",
            verified=True,
            resolution_id=res_id,
        )
        assert res.id == res_id

        context1_updated = service_session_2.retrieve_customer_context(customer_id=cust1_id)
        assert len(context1_updated.ranked_tickets[0].resolutions) == 1
        assert context1_updated.ranked_tickets[0].resolutions[0].id == res_id

    finally:
        # Strictly isolated cleanup of test nodes
        clean_entities = [
            ("Resolution", res_id),
            ("TroubleshootingStep", step1_id),
            ("Message", msg_id),
            ("Conversation", conv_id),
            ("SupportTicket", tkt_id),
            ("Issue", iss_id),
            ("Product", prod_id),
            ("Customer", cust1_id),
            ("Customer", cust2_id),
        ]
        with manager.session(database=database) as session:
            for label, eid in clean_entities:
                session.run(f"MATCH (n:{label} {{id: $id}}) DETACH DELETE n", {"id": eid})
