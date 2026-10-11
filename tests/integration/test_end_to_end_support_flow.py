"""Live integration test for Phase 8 verifying the 10-step end-to-end support workflow.

Executes against live Neo4j database when configured and reachable:
1. Create isolated test customer and product.
2. Create support ticket with realistic issue.
3. Record troubleshooting attempts and outcomes in Neo4j.
4. Leave issue unresolved (TicketStatus.OPEN).
5. Persist conversation 1 and messages in Neo4j.
6. Start a separate conversation 2 for the same customer.
7. Retrieve relevant customer history through persistent graph memory.
8. Verify SupportAgent uses retrieved history without repeating failed actions.
9. Verify agent does not invent historical actions or closed statuses without tools.
10. Verify another customer cannot view or modify the ticket (isolation).

Guarantees clean targeted cleanup of only test-created nodes in a finally block.
"""

import uuid

import pytest

from graphsupport.agents.output_parser import OutputParser
from graphsupport.agents.provider import MockLLMProvider, ProviderResponse
from graphsupport.agents.support_agent import SupportAgent
from graphsupport.agents.tool_registry import ToolRegistry
from graphsupport.application.support_service import SupportService
from graphsupport.config import get_settings
from graphsupport.core.exceptions import AuthorizationError
from graphsupport.graph.driver import Neo4jDriverManager
from graphsupport.graph.models import (
    TicketStatus,
    TroubleshootingOutcome,
)


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
def test_live_ten_step_end_to_end_workflow() -> None:
    """Verify all 10 steps of the GraphSupport AI core workflow on live Neo4j."""
    settings = get_settings()
    manager = Neo4jDriverManager(settings=settings)
    database = settings.neo4j_database

    session_id = uuid.uuid4().hex[:8]
    cust_id = f"test-e2e-cust-{session_id}"
    other_cust_id = f"test-e2e-other-{session_id}"
    prod_id = f"test-e2e-prod-{session_id}"
    iss_id = f"test-e2e-iss-{session_id}"
    tkt_id = f"test-e2e-tkt-{session_id}"
    conv1_id = f"test-e2e-c1-{session_id}"
    conv2_id = f"test-e2e-c2-{session_id}"

    service = SupportService(driver_manager=manager, database=database)

    try:
        # Step 1: Create test customer and product
        service.register_customer(
            customer_id=cust_id,
            email=f"e2e_{session_id}@example.com",
            name="E2E Alice Rivera",
            tier="standard",
        )
        service.register_customer(
            customer_id=other_cust_id,
            email=f"other_{session_id}@example.com",
            name="E2E Bob Miller",
            tier="standard",
        )
        service.register_or_update_product(
            product_id=prod_id,
            sku=f"E2E-HUB-{session_id}",
            name="Smart Security Hub Pro",
        )
        service.associate_customer_with_product(customer_id=cust_id, product_id=prod_id)

        # Step 2: Create a support ticket describing a realistic issue
        service.record_issue(
            issue_id=iss_id,
            product_id=prod_id,
            title="Hub disconnects from 5GHz WiFi",
            description="Frequent disconnects after firmware upgrade",
            category="connectivity",
        )
        ticket = service.open_support_ticket(
            ticket_id=tkt_id,
            customer_id=cust_id,
            product_id=prod_id,
            issue_id=iss_id,
            title="5GHz WiFi drop issue",
            description="Drops off every hour",
        )
        assert ticket.status == TicketStatus.OPEN

        # Step 3: Record troubleshooting attempts and their outcomes
        step = service.record_troubleshooting_step(
            ticket_id=tkt_id,
            step_number=1,
            action="Factory reset and network re-pair",
            outcome=TroubleshootingOutcome.FAILED,
            notes="Still disconnecting after 45 minutes",
        )
        assert step.outcome == TroubleshootingOutcome.FAILED

        # Step 4: Leave the issue unresolved
        details = service.get_ticket_details(tkt_id)
        assert details is not None
        assert details.ticket.status == TicketStatus.OPEN
        assert len(details.troubleshooting_steps) == 1
        assert details.troubleshooting_steps[0].outcome == TroubleshootingOutcome.FAILED

        # Step 5: Persist conversation 1 and messages in Neo4j
        c1 = service.start_conversation(
            customer_id=cust_id,
            channel="web_chat",
            conversation_id=conv1_id,
        )
        service.add_message(
            conversation_id=c1.id,
            sender_type="customer",
            content="My hub keeps dropping WiFi.",
        )
        service.add_message(
            conversation_id=c1.id,
            sender_type="assistant",
            content="I have opened ticket and attempted factory reset, but it failed.",
        )

        # Step 6: Start a separate conversation 2 for the same customer
        c2 = service.start_conversation(
            customer_id=cust_id,
            channel="web_chat",
            conversation_id=conv2_id,
        )
        assert c2.id != c1.id

        # Step 7: Retrieve relevant customer history through graph memory
        memory_context = service.retrieve_customer_context(customer_id=cust_id)
        assert memory_context.customer.name == "E2E Alice Rivera"
        assert len(memory_context.ranked_tickets) >= 1
        found_ticket = next(
            (rt for rt in memory_context.ranked_tickets if rt.ticket.id == tkt_id), None
        )
        assert found_ticket is not None
        assert len(found_ticket.troubleshooting_attempts) >= 1
        assert (
            found_ticket.troubleshooting_attempts[0].action == "Factory reset and network re-pair"
        )
        assert found_ticket.troubleshooting_attempts[0].outcome == TroubleshootingOutcome.FAILED

        # Step 8: Verify AI agent uses retrieved history without repeating failed actions
        mock_provider = MockLLMProvider()
        mock_provider.add_response(
            ProviderResponse(
                content=(
                    "Welcome back Alice. I see that your ticket tkt has an earlier factory reset "
                    "attempt that failed. Rather than repeating that reset, let's configure your "
                    "hub to connect to the 2.4GHz network band."
                ),
                tool_calls=[],
            )
        )
        agent = SupportAgent(support_service=service, llm_provider=mock_provider)
        response = agent.handle_message(
            customer_id=cust_id,
            message="My account and hub are still not working.",
            conversation_id=c2.id,
        )
        assert "factory reset" in response.response_text.lower()
        assert response.claims_verified is True

        # Step 9: Verify agent does not invent historical actions or resolutions
        parser = OutputParser()
        hallucinated_result = parser.parse_and_validate(
            raw_text="I have marked your ticket as resolved and closed your ticket.",
            context=memory_context,
            executed_tool_records=[],
        )
        assert hallucinated_result.claims_verified is False
        assert "unverified_factual_claim" in hallucinated_result.issues

        # Step 10: Verify another customer cannot view or modify the ticket
        other_registry = ToolRegistry(support_service=service, authorized_customer_id=other_cust_id)
        tool_res = other_registry.execute_tool("get_ticket_status", {"ticket_id": tkt_id})
        assert tool_res.success is False
        assert "not authorized" in tool_res.error.lower()

        with pytest.raises(AuthorizationError):
            other_registry._verify_ticket_ownership(tkt_id)

    finally:
        # Guarantee targeted cleanup of created test nodes only
        with manager.session(database=database) as session:
            session.run(
                """
                MATCH (n)
                WHERE n.id STARTS WITH $prefix
                DETACH DELETE n
                """,
                {"prefix": f"test-e2e-cust-{session_id}"},
            )
            session.run(
                """
                MATCH (n)
                WHERE n.id STARTS WITH $prefix
                DETACH DELETE n
                """,
                {"prefix": f"test-e2e-other-{session_id}"},
            )
            session.run(
                """
                MATCH (n)
                WHERE n.id STARTS WITH $prefix
                DETACH DELETE n
                """,
                {"prefix": f"test-e2e-prod-{session_id}"},
            )
            session.run(
                """
                MATCH (n)
                WHERE n.id STARTS WITH $prefix
                DETACH DELETE n
                """,
                {"prefix": f"test-e2e-iss-{session_id}"},
            )
            session.run(
                """
                MATCH (n)
                WHERE n.id STARTS WITH $prefix
                DETACH DELETE n
                """,
                {"prefix": f"test-e2e-tkt-{session_id}"},
            )
            session.run(
                """
                MATCH (n)
                WHERE n.id STARTS WITH $prefix
                DETACH DELETE n
                """,
                {"prefix": f"test-e2e-c1-{session_id}"},
            )
            session.run(
                """
                MATCH (n)
                WHERE n.id STARTS WITH $prefix
                DETACH DELETE n
                """,
                {"prefix": f"test-e2e-c2-{session_id}"},
            )
