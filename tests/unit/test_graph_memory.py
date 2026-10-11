"""Unit tests for Phase 4 Persistent Graph Memory & Context Retrieval.

Validates deterministic relevance ranking, context bounding, troubleshooting outcome
preservation (failed remains failed), customer ownership validation, empty state handling,
database failure propagation, and safe JSON serialization.
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from graphsupport.core.exceptions import (
    AuthorizationError,
    EntityNotFoundError,
    RepositoryError,
    ValidationError,
)
from graphsupport.graph.models import (
    Customer,
    Issue,
    Product,
    SupportTicket,
    TicketStatus,
    TroubleshootingOutcome,
    TroubleshootingStep,
)
from graphsupport.memory.context_builder import ContextBuilder
from graphsupport.memory.history_retriever import (
    HistoryRetriever,
    RawCustomerHistory,
    RawTicketRecord,
)
from graphsupport.memory.memory_writer import MemoryWriter
from graphsupport.memory.models import (
    RetrievalLimits,
)
from graphsupport.memory.relevance_ranker import RelevanceRanker


@pytest.fixture
def sample_customer() -> Customer:
    return Customer(
        id="cust-100",
        email="test@example.com",
        name="Alex Mercer",
        tier="pro",
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
    )


@pytest.fixture
def sample_product() -> Product:
    return Product(
        id="prod-netgear",
        sku="ROUTER-X1",
        name="NetGear Gateway X1",
        category="Networking",
    )


@pytest.fixture
def sample_issue(sample_product: Product) -> Issue:
    return Issue(
        id="issue-wifi-drop",
        product_id=sample_product.id,
        title="WiFi Drop Problem",
        summary="WiFi dropped connection constantly",
        category="connectivity",
        severity="high",
    )


@pytest.fixture
def active_ticket(
    sample_customer: Customer, sample_product: Product, sample_issue: Issue
) -> SupportTicket:
    return SupportTicket(
        id="tick-active-1",
        customer_id=sample_customer.id,
        product_id=sample_product.id,
        issue_id=sample_issue.id,
        title="Router keeps dropping connection",
        description="Every 10 minutes connection resets",
        status=TicketStatus.IN_PROGRESS,
        priority="high",
        created_at=datetime.now(UTC) - timedelta(hours=2),
        updated_at=datetime.now(UTC) - timedelta(minutes=15),
    )


@pytest.fixture
def resolved_ticket(
    sample_customer: Customer, sample_product: Product, sample_issue: Issue
) -> SupportTicket:
    return SupportTicket(
        id="tick-resolved-2",
        customer_id=sample_customer.id,
        product_id=sample_product.id,
        issue_id=sample_issue.id,
        title="Old connection issue from last month",
        description="Resolved with reboot",
        status=TicketStatus.RESOLVED,
        priority="medium",
        created_at=datetime.now(UTC) - timedelta(days=30),
        updated_at=datetime.now(UTC) - timedelta(days=29),
    )


# =============================================================================
# Relevance Ranker Tests
# =============================================================================


class TestRelevanceRanker:
    """Test deterministic scoring rules without LLM or vector components."""

    def test_active_ticket_ranks_higher_than_resolved(
        self,
        active_ticket: SupportTicket,
        resolved_ticket: SupportTicket,
        sample_product: Product,
        sample_issue: Issue,
    ) -> None:
        ranker = RelevanceRanker()

        rec_active = RawTicketRecord(
            ticket=active_ticket,
            product=sample_product,
            issue=sample_issue,
        )
        rec_resolved = RawTicketRecord(
            ticket=resolved_ticket,
            product=sample_product,
            issue=sample_issue,
        )

        ranked = ranker.rank_tickets(
            ticket_records=[rec_resolved, rec_active],
            queried_ticket_id=None,
            queried_product_id=None,
            issue_query=None,
        )

        assert len(ranked) == 2
        assert ranked[0].ticket.id == active_ticket.id
        assert ranked[0].relevance_score > ranked[1].relevance_score

    def test_explicit_ticket_id_receives_highest_boost(
        self,
        active_ticket: SupportTicket,
        resolved_ticket: SupportTicket,
        sample_product: Product,
        sample_issue: Issue,
    ) -> None:
        ranker = RelevanceRanker()

        rec_active = RawTicketRecord(
            ticket=active_ticket, product=sample_product, issue=sample_issue
        )
        rec_resolved = RawTicketRecord(
            ticket=resolved_ticket, product=sample_product, issue=sample_issue
        )

        # Explicitly query for the resolved ticket
        ranked = ranker.rank_tickets(
            ticket_records=[rec_active, rec_resolved],
            queried_ticket_id=resolved_ticket.id,
        )

        assert ranked[0].ticket.id == resolved_ticket.id
        assert any("explicit_ticket_match" in factor for factor in ranked[0].ranking_reasons)

    def test_product_and_issue_query_scoring(
        self,
        active_ticket: SupportTicket,
        sample_product: Product,
        sample_issue: Issue,
    ) -> None:
        ranker = RelevanceRanker()
        rec = RawTicketRecord(ticket=active_ticket, product=sample_product, issue=sample_issue)

        # Match product and issue query keywords
        ranked = ranker.rank_tickets(
            ticket_records=[rec],
            queried_product_id=sample_product.id,
            issue_query="wifi connection dropping",
            customer_product_ids={sample_product.id},
        )

        assert len(ranked) == 1
        factors = " ".join(ranked[0].ranking_reasons)
        assert "queried_product_match" in factors
        assert "issue_keyword_match" in factors

    def test_failed_troubleshooting_attempt_weight(
        self,
        active_ticket: SupportTicket,
        sample_product: Product,
        sample_issue: Issue,
    ) -> None:
        ranker = RelevanceRanker()
        failed_step = TroubleshootingStep(
            id="step-1",
            ticket_id=active_ticket.id,
            step_number=1,
            action="Factory Reset",
            outcome=TroubleshootingOutcome.FAILED,
            notes="Reset did not fix drops",
        )
        rec_with_fail = RawTicketRecord(
            ticket=active_ticket,
            product=sample_product,
            issue=sample_issue,
            attempts=[failed_step],
        )

        ranked = ranker.rank_tickets([rec_with_fail])
        assert any("has_failed_attempts" in factor for factor in ranked[0].ranking_reasons)


# =============================================================================
# Context Builder & Outcome Fidelity Tests
# =============================================================================


class TestContextBuilder:
    """Test bounded context assembly, indicators, and outcome fidelity."""

    def test_failed_outcome_remains_strictly_failed(
        self,
        sample_customer: Customer,
        sample_product: Product,
        sample_issue: Issue,
        active_ticket: SupportTicket,
    ) -> None:
        builder = ContextBuilder()
        failed_step = TroubleshootingStep(
            id="step-1",
            ticket_id=active_ticket.id,
            step_number=1,
            action="Reboot Modem",
            outcome=TroubleshootingOutcome.FAILED,
            notes="No signal after reboot",
        )
        success_step = TroubleshootingStep(
            id="step-2",
            ticket_id=active_ticket.id,
            step_number=2,
            action="Firmware Upgrade",
            outcome=TroubleshootingOutcome.SUCCESS,
            notes="Upgraded to v1.2",
        )

        rec = RawTicketRecord(
            ticket=active_ticket,
            product=sample_product,
            issue=sample_issue,
            attempts=[failed_step, success_step],
        )
        raw_history = RawCustomerHistory(
            customer=sample_customer,
            products=[sample_product],
            ticket_records=[rec],
            conversations=[],
        )

        context = builder.build_memory_context(raw_history)
        ranked_t = context.ranked_tickets[0]

        assert len(ranked_t.troubleshooting_attempts) == 2
        # Verify outcomes were not mutated or inverted
        step1 = next(a for a in ranked_t.troubleshooting_attempts if a.step_number == 1)
        step2 = next(a for a in ranked_t.troubleshooting_attempts if a.step_number == 2)
        assert step1.outcome == TroubleshootingOutcome.FAILED
        assert step2.outcome == TroubleshootingOutcome.SUCCESS

        # Check missing info indicators flagged the failed attempt
        assert any("has_failed_attempt_step_1" in flag for flag in context.missing_information)

    def test_empty_customer_history_handling(self, sample_customer: Customer) -> None:
        builder = ContextBuilder()
        raw_history = RawCustomerHistory(
            customer=sample_customer,
            products=[],
            ticket_records=[],
            conversations=[],
        )

        context = builder.build_memory_context(raw_history)

        assert context.customer.id == sample_customer.id
        assert context.products == []
        assert context.ranked_tickets == []
        assert context.recent_conversations == []
        assert "customer_has_no_registered_products" in context.missing_information
        assert "no_support_tickets_found" in context.missing_information

    def test_context_limits_and_bounding(
        self,
        sample_customer: Customer,
        sample_product: Product,
        sample_issue: Issue,
    ) -> None:
        builder = ContextBuilder()
        records = []
        for i in range(10):
            ticket = SupportTicket(
                id=f"tick-{i}",
                customer_id=sample_customer.id,
                product_id=sample_product.id,
                issue_id=sample_issue.id,
                title=f"Ticket {i}",
                description="Sample description " * 10,
                status=TicketStatus.OPEN,
                priority="medium",
                created_at=datetime.now(UTC),
            )
            records.append(
                RawTicketRecord(ticket=ticket, product=sample_product, issue=sample_issue)
            )

        raw_history = RawCustomerHistory(
            customer=sample_customer,
            products=[sample_product],
            ticket_records=records,
            conversations=[],
        )

        # Apply strict limit of 3 tickets
        limits = RetrievalLimits(max_tickets=3)
        context = builder.build_memory_context(raw_history, limits=limits)

        assert len(context.ranked_tickets) == 3
        assert context.retrieval_metadata.total_tickets_found == 10
        assert context.retrieval_metadata.tickets_included == 3

    def test_safe_serialization_to_dict_and_json(
        self,
        sample_customer: Customer,
        sample_product: Product,
        sample_issue: Issue,
        active_ticket: SupportTicket,
    ) -> None:
        builder = ContextBuilder()
        rec = RawTicketRecord(ticket=active_ticket, product=sample_product, issue=sample_issue)
        raw_history = RawCustomerHistory(
            customer=sample_customer,
            products=[sample_product],
            ticket_records=[rec],
            conversations=[],
        )

        context = builder.build_memory_context(raw_history)
        data_dict = context.to_dict()

        # Must be valid json encodable
        json_str = json.dumps(data_dict)
        assert json_str is not None

        # Verify essential fields in serialized representation
        assert data_dict["customer"]["id"] == sample_customer.id
        assert len(data_dict["ranked_tickets"]) == 1
        assert data_dict["ranked_tickets"][0]["ticket"]["id"] == active_ticket.id
        assert "relevance_score" in data_dict["ranked_tickets"][0]
        assert "ranking_reasons" in data_dict["ranked_tickets"][0]


# =============================================================================
# History Retriever Ownership & Validation Tests
# =============================================================================


class TestHistoryRetrieverGuards:
    """Test validation, authorization boundaries, and failure propagation."""

    def test_empty_customer_id_raises_validation_error(self) -> None:
        mock_dm = MagicMock()
        retriever = HistoryRetriever(driver_manager=mock_dm)

        with pytest.raises(ValidationError, match="Customer ID cannot be empty"):
            retriever.retrieve_raw_history(customer_id="")

    def test_nonexistent_customer_raises_entity_not_found(self) -> None:
        mock_dm = MagicMock()
        mock_session = MagicMock()
        mock_dm.session.return_value.__enter__.return_value = mock_session

        # Run returns no customer record
        mock_result = MagicMock()
        mock_result.single.return_value = None
        mock_session.run.return_value = mock_result

        retriever = HistoryRetriever(driver_manager=mock_dm)

        with pytest.raises(EntityNotFoundError, match="Customer with ID 'cust-999' does not exist"):
            retriever.retrieve_raw_history(customer_id="cust-999")

    def test_ticket_ownership_violation_raises_authorization_error(self) -> None:
        mock_dm = MagicMock()
        mock_session = MagicMock()
        mock_dm.session.return_value.__enter__.return_value = mock_session

        # 1. Customer found
        mock_c_record = {
            "id": "cust-1",
            "email": "cust1@example.com",
            "name": "Cust One",
            "tier": "standard",
            "created_at": datetime.now(UTC),
            "metadata": {},
        }
        # 2. Ticket check returns ticket exists but owned is False
        mock_t_record = {
            "exists": True,
            "owned": False,
        }

        mock_res1 = MagicMock()
        mock_res1.single.return_value = mock_c_record

        mock_res2 = MagicMock()
        mock_res2.single.return_value = mock_t_record

        mock_session.run.side_effect = [mock_res1, mock_res2]

        retriever = HistoryRetriever(driver_manager=mock_dm)

        with pytest.raises(AuthorizationError, match="is not authorized to access ticket"):
            retriever.retrieve_raw_history(customer_id="cust-1", ticket_id="tick-alien")

    def test_database_error_propagates_as_repository_error(self) -> None:
        mock_dm = MagicMock()
        mock_session = MagicMock()
        mock_dm.session.return_value.__enter__.return_value = mock_session

        from neo4j.exceptions import ServiceUnavailable

        mock_session.run.side_effect = ServiceUnavailable("Neo4j database connection lost")

        retriever = HistoryRetriever(driver_manager=mock_dm)

        with pytest.raises(RepositoryError, match="history retrieval"):
            retriever.retrieve_raw_history(customer_id="cust-1")


# =============================================================================
# Memory Writer Tests
# =============================================================================


class TestMemoryWriter:
    """Verify safe write coordination through SupportService."""

    def test_memory_writer_delegates_to_service(self) -> None:
        mock_service = MagicMock()
        writer = MemoryWriter(support_service=mock_service)

        writer.record_troubleshooting_attempt(
            ticket_id="tick-1",
            step_number=1,
            action="Power Cycle",
            outcome=TroubleshootingOutcome.FAILED,
            notes="Still blinking red",
        )
        mock_service.record_troubleshooting_step.assert_called_once()

        writer.record_verified_resolution(
            ticket_id="tick-1",
            summary="Replaced blown capacitor",
            resolution_type="hardware_repair",
            verified=True,
        )
        mock_service.record_ticket_resolution.assert_called_once()
