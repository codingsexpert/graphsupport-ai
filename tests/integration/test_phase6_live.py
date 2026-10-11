"""Live Neo4j Aura integration tests for Phase 6 Support Dashboard."""

import pytest

from graphsupport.application.evaluation import EvaluationRunner
from graphsupport.application.support_service import SupportService
from graphsupport.config import get_settings
from graphsupport.graph.driver import get_driver_manager


@pytest.mark.integration
def test_live_phase6_dashboard_service_methods() -> None:
    """Verify live Neo4j Aura execution of Phase 6 dashboard operations."""
    settings = get_settings()
    if not settings.is_neo4j_configured:
        pytest.skip("Neo4j is not configured in .env")

    dm = get_driver_manager(settings=settings)
    if not dm.verify_connectivity():
        pytest.skip("Neo4j instance unreachable")

    service = SupportService(driver_manager=dm, database=settings.neo4j_database)

    # 1. Overview metrics
    metrics = service.get_overview_metrics()
    assert "total_customers" in metrics
    assert "total_tickets" in metrics
    assert "open_tickets" in metrics
    assert "in_progress_tickets" in metrics
    assert "resolved_tickets" in metrics
    assert isinstance(metrics["total_customers"], int)
    assert isinstance(metrics["total_tickets"], int)
    assert isinstance(metrics["recent_tickets"], list)
    assert isinstance(metrics["recent_steps"], list)
    assert isinstance(metrics["recent_resolutions"], list)

    # 2. List all tickets
    tickets = service.list_all_tickets(limit=10)
    assert isinstance(tickets, list)

    # 3. List all conversations
    conversations = service.list_all_conversations(limit=10)
    assert isinstance(conversations, list)

    # 4. Get Subgraph
    subgraph = service.get_subgraph(max_nodes=20)
    assert "nodes" in subgraph
    assert "edges" in subgraph
    assert isinstance(subgraph["nodes"], list)
    assert isinstance(subgraph["edges"], list)

    # 5. Run Evaluation benchmarks against live service
    runner = EvaluationRunner(service=service)
    report = runner.run_all_evaluations()
    assert report.total_tests == 9
    assert report.passed_tests == 9
    assert report.overall_score == 1.0
