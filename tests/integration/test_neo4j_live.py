"""Live integration tests against configured Neo4j instance.

Operates exclusively using unique test keys ('test-phase2-<uuid>') and guarantees
that only exact test records created by the suite are cleaned up.
Automatically skips with clear reporting if Neo4j is unreachable or unconfigured.
"""

import uuid

import pytest

from graphsupport.config import get_settings
from graphsupport.graph.driver import Neo4jDriverManager
from graphsupport.graph.models import Customer
from graphsupport.graph.repository import CustomerRepository
from graphsupport.graph.schema import initialize_schema, inspect_schema


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
def test_live_neo4j_connectivity() -> None:
    """Verify live connectivity and server info from configured Neo4j instance."""
    settings = get_settings()
    manager = Neo4jDriverManager(settings=settings)
    assert manager.verify_connectivity() is True

    info = manager.get_server_info()
    assert "agent" in info
    assert "protocol_version" in info


@pytest.mark.skipif(not live_neo4j_available, reason=skip_reason)
def test_live_schema_initialization_idempotent() -> None:
    """Verify idempotent schema initialization against live Neo4j database."""
    settings = get_settings()
    manager = Neo4jDriverManager(settings=settings)

    # First run
    report1 = initialize_schema(manager.get_driver(), database=settings.neo4j_database)
    assert report1.is_successful is True
    assert report1.succeeded == report1.total

    # Second run must be completely idempotent
    report2 = initialize_schema(manager.get_driver(), database=settings.neo4j_database)
    assert report2.is_successful is True

    # Check inspection returns created constraints
    inspection = inspect_schema(manager.get_driver(), database=settings.neo4j_database)
    assert len(inspection["constraints"]) > 0


@pytest.mark.skipif(not live_neo4j_available, reason=skip_reason)
def test_live_customer_crud_and_cleanup() -> None:
    """Verify customer upsert, retrieval by ID/email, and safe isolated cleanup."""
    settings = get_settings()
    manager = Neo4jDriverManager(settings=settings)
    repo = CustomerRepository(driver_manager=manager, database=settings.neo4j_database)

    # Unique test-isolated customer ID and email
    unique_suffix = uuid.uuid4().hex[:12]
    test_id = f"test-phase2-{unique_suffix}"
    test_email = f"test-user-{unique_suffix}@graphsupport.test"

    customer = Customer(
        id=test_id,
        email=test_email,
        name="Integration Test User",
        tier="enterprise",
        metadata={"suite": "phase2_integration", "temp": True},
    )

    try:
        # 1. Create / Upsert
        saved = repo.upsert_customer(customer)
        assert saved.id == test_id
        assert saved.email == test_email
        assert saved.tier == "enterprise"

        # 2. Retrieve by ID
        fetched_by_id = repo.get_by_id(test_id)
        assert fetched_by_id is not None
        assert fetched_by_id.id == test_id
        assert fetched_by_id.email == test_email
        assert fetched_by_id.name == "Integration Test User"

        # 3. Retrieve by email
        fetched_by_email = repo.get_by_email(test_email)
        assert fetched_by_email is not None
        assert fetched_by_email.id == test_id

    finally:
        # 4. Strictly isolated cleanup: delete only the exact test record created
        deleted = repo.delete_by_id(test_id)
        assert deleted is True

        # Verify deletion
        assert repo.get_by_id(test_id) is None
