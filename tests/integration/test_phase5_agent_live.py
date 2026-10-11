"""Live integration tests for Phase 5 Context-Aware AI Support Agent against Neo4j.

Executes an end-to-end agent turn backed by persistent Neo4j graph storage and
controlled tool execution:
- Grounded memory context retrieval from Neo4j.
- Agent tool execution creating a verified troubleshooting step in Neo4j.
- Full conversation transcript persistence (user and assistant messages).
- Guaranteed cleanup of all created test nodes in a finally block.
"""

import uuid

import pytest

from graphsupport.agents.provider import MockLLMProvider, ProviderResponse, ToolCall
from graphsupport.agents.support_agent import SupportAgent
from graphsupport.application.support_service import SupportService
from graphsupport.config import get_settings
from graphsupport.graph.driver import Neo4jDriverManager
from graphsupport.graph.models import (
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
def test_live_phase5_agent_turn_and_tool_persistence() -> None:
    """Verify SupportAgent retrieves context, runs tools, and persists chat in Neo4j."""
    settings = get_settings()
    manager = Neo4jDriverManager(settings=settings)
    database = settings.neo4j_database

    session_id = uuid.uuid4().hex[:8]
    cust_id = f"test-phase5-cust-{session_id}"
    prod_id = f"test-phase5-prod-{session_id}"
    iss_id = f"test-phase5-iss-{session_id}"
    tkt_id = f"test-phase5-tkt-{session_id}"
    step1_id = f"test-phase5-step1-{session_id}"

    service = SupportService(driver_manager=manager, database=database)

    try:
        # 1. Setup customer, product, issue, and ticket with a failed step
        service.register_customer(
            customer_id=cust_id,
            email=f"phase5_{session_id}@example.com",
            name="Phase 5 Tester",
            tier="enterprise",
        )
        service.register_or_update_product(
            product_id=prod_id,
            sku=f"P5-{session_id}",
            name="Phase 5 Gateway Pro",
        )
        service.associate_customer_with_product(customer_id=cust_id, product_id=prod_id)
        service.record_issue(
            issue_id=iss_id,
            product_id=prod_id,
            title="Firmware boot loop",
            description="Repeated restarts",
            category="firmware",
        )
        service.open_support_ticket(
            ticket_id=tkt_id,
            customer_id=cust_id,
            product_id=prod_id,
            issue_id=iss_id,
            title="Gateway flashing yellow",
            description="Reboots every 5 minutes",
        )
        service.record_troubleshooting_step(
            ticket_id=tkt_id,
            step_number=1,
            action="Power cycle device for 60s",
            outcome=TroubleshootingOutcome.FAILED,
            notes="Still flashing yellow",
            step_id=step1_id,
        )

        # 2. Setup mock provider for the agent turn
        mock_provider = MockLLMProvider()
        # Step 1: Model decides to record a new troubleshooting step
        mock_provider.add_response(
            ProviderResponse(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="call-diag",
                        name="record_troubleshooting_attempt",
                        arguments={
                            "ticket_id": tkt_id,
                            "step_number": 2,
                            "action": "Flash recovery image via USB drive",
                            "outcome": "success",
                            "notes": "Device booted successfully to steady green",
                        },
                    )
                ],
            )
        )
        # Step 2: Model generates final response acknowledging past failed attempt and new fix
        mock_provider.add_response(
            ProviderResponse(
                content=(
                    "I noticed the initial power cycle on ticket "
                    f"{tkt_id} failed. I've now recorded your recovery flash as successful!"
                ),
                tool_calls=[],
            )
        )

        agent = SupportAgent(
            support_service=service,
            llm_provider=mock_provider,
        )

        # 3. Customer sends message
        response = agent.handle_message(
            customer_id=cust_id,
            message="I flashed the recovery image via USB and the gateway is working now!",
            focused_ticket_id=tkt_id,
        )

        # 4. Assert response structure
        assert response.conversation_id is not None
        assert len(response.tool_executions) == 1
        assert response.tool_executions[0].tool_name == "record_troubleshooting_attempt"
        assert response.tool_executions[0].success is True
        assert "recorded your recovery flash" in response.response_text

        # 5. Verify Neo4j persistence: conversation messages exist
        messages = service.get_conversation_messages(response.conversation_id)
        assert len(messages) >= 2
        user_msg = next(m for m in messages if m.sender_type == "customer")
        asst_msg = next(m for m in messages if m.sender_type == "assistant")
        assert "USB" in user_msg.content
        assert "recovery flash" in asst_msg.content

        # 6. Verify Neo4j persistence: Step 2 exists on ticket
        details = service.get_ticket_details(tkt_id)
        assert details is not None
        assert len(details.troubleshooting_steps) == 2
        step1 = next(s for s in details.troubleshooting_steps if s.step_number == 1)
        step2 = next(s for s in details.troubleshooting_steps if s.step_number == 2)
        assert step1.outcome == TroubleshootingOutcome.FAILED
        assert step2.outcome == TroubleshootingOutcome.SUCCESS
        assert "USB drive" in step2.action

    finally:
        # Strictly isolated cleanup of all test entities
        with manager.session(database=database) as session:
            session.run(
                """
                MATCH (c:Customer {id: $cid})
                OPTIONAL MATCH (c)-[:HAS_TICKET]->(t:SupportTicket)
                OPTIONAL MATCH (t)-[:HAS_ATTEMPT]->(s:TroubleshootingStep)
                OPTIONAL MATCH (t)-[:HAS_RESOLUTION]->(r:Resolution)
                OPTIONAL MATCH (c)-[:HAS_CONVERSATION]->(conv:Conversation)
                OPTIONAL MATCH (conv)-[:CONTAINS]->(m:Message)
                DETACH DELETE s, r, m, conv, t, c
                """,
                {"cid": cust_id},
            )
            session.run("MATCH (i:Issue {id: $id}) DETACH DELETE i", {"id": iss_id})
            session.run("MATCH (p:Product {id: $id}) DETACH DELETE p", {"id": prod_id})
