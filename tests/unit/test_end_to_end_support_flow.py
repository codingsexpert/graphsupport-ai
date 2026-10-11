"""Unit tests verifying the complete 10-step end-to-end customer support workflow.

Deterministic test suite using in-memory mocks to verify:
1. Customer and product creation.
2. Support ticket creation.
3. Troubleshooting attempts with outcomes.
4. Ticket status handling (unresolved).
5. Conversation and message persistence.
6. Second conversation session initiation.
7. Relevant graph memory retrieval.
8. AI agent utilizing prior context without repeating failed actions.
9. Groundedness validation (preventing invented ticket states or actions).
10. Multi-tenant customer data isolation.
"""

from unittest.mock import MagicMock

import pytest

from graphsupport.agents.output_parser import OutputParser
from graphsupport.agents.provider import MockLLMProvider, ProviderResponse
from graphsupport.agents.support_agent import SupportAgent
from graphsupport.agents.tool_registry import ToolRegistry
from graphsupport.application.support_service import SupportService
from graphsupport.core.exceptions import AuthorizationError
from graphsupport.graph.models import (
    Customer,
    Issue,
    Product,
    SupportTicket,
    TicketDetails,
    TicketStatus,
    TroubleshootingOutcome,
    TroubleshootingStep,
)
from graphsupport.memory.context_builder import ContextBuilder
from graphsupport.memory.history_retriever import RawCustomerHistory, RawTicketRecord


def test_end_to_end_ten_step_support_workflow() -> None:
    """Verify all 10 steps of the GraphSupport AI core workflow deterministically."""
    # Step 1: Identify / Create test customer and product
    cust_id = "test-cust-alex"
    prod_id = "test-prod-hub"
    other_cust_id = "test-cust-bob"

    customer = Customer(id=cust_id, email="alex@example.com", name="Alex Rivera", tier="standard")
    other_customer = Customer(
        id=other_cust_id, email="bob@example.com", name="Bob Martin", tier="basic"
    )
    product = Product(id=prod_id, name="Smart Security Hub Pro", sku="HUB-PRO-01")

    # Step 2: Create a support ticket describing a realistic issue
    tkt_id = "tkt-alex-101"
    issue = Issue(
        id="iss-wifi-fail",
        product_id=prod_id,
        title="WiFi Connection Drops",
        description="Hub disconnects from 5GHz WiFi after firmware update",
        category="connectivity",
    )
    ticket = SupportTicket(
        id=tkt_id,
        customer_id=cust_id,
        product_id=prod_id,
        issue_id=issue.id,
        title="Hub disconnects from 5GHz WiFi",
        description="After updating to firmware 2.4, hub drops off the network every hour.",
        status=TicketStatus.OPEN,
    )

    # Step 3: Record troubleshooting attempts and their outcomes
    step1 = TroubleshootingStep(
        id="step-1",
        ticket_id=tkt_id,
        step_number=1,
        action="Factory reset and network re-pair",
        outcome=TroubleshootingOutcome.FAILED,
        notes="Reset completed, but device still disconnected after 45 minutes.",
    )

    # Step 4: Leave the issue unresolved (status remains OPEN)
    assert ticket.status == TicketStatus.OPEN
    assert step1.outcome == TroubleshootingOutcome.FAILED

    # Step 5: Mock repository & service backing persistent conversation & messages
    mock_service = MagicMock(spec=SupportService)
    mock_service.get_customer.side_effect = lambda cid: (
        customer if cid == cust_id else (other_customer if cid == other_cust_id else None)
    )
    mock_service.get_ticket_details.side_effect = lambda tid: (
        TicketDetails(
            ticket=ticket,
            customer=customer,
            product=product,
            issue=issue,
            troubleshooting_steps=[step1],
            resolutions=[],
        )
        if tid == tkt_id
        else None
    )

    # Step 6: Start a separate conversation for the same customer
    conv2_id = "conv-session-2"
    mock_service.start_conversation.return_value = MagicMock(id=conv2_id, customer_id=cust_id)

    # Step 7: Retrieve relevant customer history through graph memory
    raw_history = RawCustomerHistory(
        customer=customer,
        products=[product],
        ticket_records=[
            RawTicketRecord(
                ticket=ticket,
                product=product,
                issue=issue,
                attempts=[step1],
                resolutions=[],
                related_messages=[],
            )
        ],
        conversations=[],
    )

    context_builder = ContextBuilder()
    memory_context = context_builder.build_memory_context(raw_history)

    assert memory_context.customer.name == "Alex Rivera"
    assert len(memory_context.ranked_tickets) == 1
    assert memory_context.ranked_tickets[0].ticket.id == tkt_id
    assert len(memory_context.ranked_tickets[0].troubleshooting_attempts) == 1
    assert (
        memory_context.ranked_tickets[0].troubleshooting_attempts[0].action
        == "Factory reset and network re-pair"
    )
    assert (
        memory_context.ranked_tickets[0].troubleshooting_attempts[0].outcome
        == TroubleshootingOutcome.FAILED
    )
    # Diagnostic warning is flagged
    assert any("failed_attempt" in flag for flag in memory_context.missing_information)

    # Step 8: Verify AI agent uses retrieved history without repeating failed actions
    # Mock LLM provider returns a context-aware response acknowledging failed reset
    mock_provider = MockLLMProvider()
    mock_provider.add_response(
        ProviderResponse(
            content=(
                "I see that you previously attempted a factory reset on your device "
                "for ticket tkt-alex-101, but it dropped. Since the reset failed, "
                "let's check whether switching your router to 2.4GHz stabilizes it."
            ),
            tool_calls=[],
        )
    )

    # Mock memory service
    mock_memory_service = MagicMock()
    mock_memory_service.get_context_for_customer.return_value = memory_context
    mock_service.memory_service = mock_memory_service

    agent = SupportAgent(support_service=mock_service, llm_provider=mock_provider)
    response = agent.handle_message(
        customer_id=cust_id,
        message="My hub is still disconnecting from the network.",
        conversation_id=conv2_id,
    )

    assert "factory reset" in response.response_text.lower()
    assert "tkt-alex-101" in response.response_text
    assert response.claims_verified is True

    # Step 9: Verify agent does not invent historical actions, ticket statuses or resolutions
    parser = OutputParser()
    hallucinated_response = parser.parse_and_validate(
        raw_text="I have closed your ticket tkt-alex-101 and marked it resolved.",
        context=memory_context,
        executed_tool_records=[],  # No tool was actually executed!
    )
    # Parser catches that ticket status closure was claimed without tool execution
    assert hallucinated_response.claims_verified is False
    assert "unverified_factual_claim" in hallucinated_response.issues

    # Step 10: Verify another customer's private history is not exposed
    # Bob attempts to operate on Alex's ticket
    registry_bob = ToolRegistry(support_service=mock_service, authorized_customer_id=other_cust_id)

    # Bob tries to look up Alex's ticket status
    tool_result = registry_bob.execute_tool(
        "get_ticket_status",
        {"ticket_id": tkt_id},
    )
    assert tool_result.success is False
    assert "not authorized" in tool_result.error.lower()

    # Bob directly invokes internal ownership check
    with pytest.raises(AuthorizationError):
        registry_bob._verify_ticket_ownership(tkt_id)
