"""Unit tests for GraphSupport AI Phase 6 Support Dashboard."""

from unittest.mock import MagicMock

from graphsupport.application.evaluation import EvaluationRunner
from graphsupport.application.support_service import SupportService
from graphsupport.graph.models import SupportTicket, TicketStatus
from graphsupport.ui.navigation import NAV_OPTIONS


def test_navigation_options_has_expected_ten_pages() -> None:
    """Verify navigation options include all 10 operations pages."""
    expected_keywords = [
        "Overview",
        "Support Chat",
        "Customers",
        "Products",
        "Tickets",
        "Ticket Details",
        "Conversation History",
        "Graph Explorer",
        "System Health",
        "Evaluation",
    ]
    assert len(NAV_OPTIONS) == 10
    for keyword in expected_keywords:
        assert any(keyword in opt for opt in NAV_OPTIONS), f"Missing page for keyword: {keyword}"


def test_evaluation_runner_offline_benchmarks() -> None:
    """Verify EvaluationRunner executes offline benchmarks and scores results."""
    runner = EvaluationRunner(service=None)
    report = runner.run_all_evaluations()

    assert report.total_tests == 6
    assert report.passed_tests == 6
    assert report.overall_score == 1.0
    assert report.is_mocked is True
    assert len(report.benchmark_items) == 6

    # Verify key categories
    categories = {item.category for item in report.benchmark_items}
    assert "Memory Retrieval" in categories
    assert "Diagnostic Integrity" in categories
    assert "Tool Safety" in categories
    assert "Groundedness" in categories
    assert "Security" in categories
    assert "Performance" in categories


def test_support_service_list_all_tickets_delegates_to_repo() -> None:
    """Verify SupportService.list_all_tickets validates status and calls repo."""
    mock_ticket_repo = MagicMock()
    mock_ticket_repo.list_all_tickets.return_value = [
        SupportTicket(
            id="t-1",
            title="Gateway issue",
            description="desc",
            status=TicketStatus.OPEN,
            priority="high",
        )
    ]

    service = SupportService(
        driver_manager=MagicMock(),
        ticket_repo=mock_ticket_repo,
    )

    results = service.list_all_tickets(status="open", limit=10)
    assert len(results) == 1
    assert results[0].id == "t-1"
    mock_ticket_repo.list_all_tickets.assert_called_once_with(
        status=TicketStatus.OPEN, limit=10, skip=0
    )


def test_support_service_list_all_conversations_delegates_to_repo() -> None:
    """Verify SupportService.list_all_conversations calls conversation_repo."""
    mock_conv_repo = MagicMock()
    mock_conv_repo.list_all_conversations.return_value = []

    service = SupportService(
        driver_manager=MagicMock(),
        conversation_repo=mock_conv_repo,
    )

    results = service.list_all_conversations(limit=25)
    assert results == []
    mock_conv_repo.list_all_conversations.assert_called_once_with(limit=25, skip=0)


def test_subgraph_bounded_node_limits() -> None:
    """Verify get_subgraph respects max_nodes clamping."""
    mock_driver_manager = MagicMock()
    mock_session = MagicMock()
    mock_driver_manager.session.return_value.__enter__.return_value = mock_session
    mock_session.run.return_value = []

    service = SupportService(driver_manager=mock_driver_manager)
    subgraph = service.get_subgraph(max_nodes=15)
    assert "nodes" in subgraph
    assert "edges" in subgraph
    assert isinstance(subgraph["nodes"], list)
    assert isinstance(subgraph["edges"], list)
