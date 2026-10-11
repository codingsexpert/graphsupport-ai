"""Reproducible Hackathon Demonstration Scenario Seeder for GraphSupport AI (Phase 8).

Seeds a realistic, end-to-end customer support scenario demonstrating the value of
persistent Neo4j graph memory:

Scenario:
Conversation 1:
- Sarah Chen reports an inability to log in to the SmartMesh cloud portal.
- Support ticket demo-tkt-101 is opened.
- Troubleshooting Step 1: Password reset link is sent.
- Outcome: FAILED (token expired immediately with HTTP 401).
- Issue remains unresolved (OPEN).
- Conversation 1 messages are stored in Neo4j.

Conversation 2:
- Sarah returns in a separate session saying: "My account still isn't working."
- The agent retrieves the previous ticket and failed attempt from Neo4j memory.
- The agent acknowledges the prior failed password reset without repeating it,
  and suggests next-level authentication diagnostics (e.g., admin token flush).

Guarantees:
- Explicit opt-in only: Never runs automatically on startup.
- Safe cleanup: Only removes nodes starting with 'demo-'. Real customer data is never touched.
"""

import logging
from typing import Any

from graphsupport.application.support_service import SupportService
from graphsupport.core.exceptions import GraphSupportError
from graphsupport.graph.models import TroubleshootingOutcome

logger = logging.getLogger("graphsupport.application.demo_seed")

DEMO_CUSTOMER_ID = "demo-cust-sarah"
DEMO_CUSTOMER_NAME = "Sarah Chen"
DEMO_CUSTOMER_EMAIL = "sarah.chen@example.com"
DEMO_CUSTOMER_TIER = "enterprise"

DEMO_PRODUCT_ID = "demo-prod-gateway"
DEMO_PRODUCT_NAME = "SmartMesh Home Gateway Pro"
DEMO_PRODUCT_SKU = "SM-GW-PRO"

DEMO_ISSUE_ID = "demo-iss-login-401"
DEMO_ISSUE_TITLE = "Cloud portal login returns HTTP 401 Unauthorized"

DEMO_TICKET_ID = "demo-tkt-101"
DEMO_TICKET_TITLE = "Unable to log in to SmartMesh cloud portal"
DEMO_TICKET_DESC = (
    "Customer cannot log in to admin portal. Password reset email tokens fail with 401."
)

DEMO_STEP_1_ID = "demo-step-101-1"
DEMO_CONV_1_ID = "demo-conv-session-1"
DEMO_CONV_2_ID = "demo-conv-session-2"


def is_hackathon_demo_seeded(service: SupportService) -> bool:
    """Check if the hackathon demo customer currently exists in the database."""
    try:
        cust = service.get_customer(DEMO_CUSTOMER_ID)
        return cust is not None
    except Exception:
        return False


def seed_hackathon_demo(service: SupportService) -> dict[str, Any]:
    """Explicitly seed the two-conversation demo scenario into Neo4j.

    Args:
        service: Active application SupportService.

    Returns:
        Summary dictionary of created demo entities.
    """
    logger.info("Starting hackathon demo data seeding...")

    # 1. Register customer
    customer = service.register_customer(
        customer_id=DEMO_CUSTOMER_ID,
        name=DEMO_CUSTOMER_NAME,
        email=DEMO_CUSTOMER_EMAIL,
        tier=DEMO_CUSTOMER_TIER,
        metadata={"persona": "Hackathon Demo User", "company": "Acme Corp"},
    )

    # 2. Register product & associate customer
    product = service.register_or_update_product(
        product_id=DEMO_PRODUCT_ID,
        name=DEMO_PRODUCT_NAME,
        sku=DEMO_PRODUCT_SKU,
        category="networking",
        version="2.4.1",
        metadata={"specs": "Wi-Fi 6E, Gigabit Ethernet"},
    )
    service.associate_customer_with_product(
        customer_id=DEMO_CUSTOMER_ID,
        product_id=DEMO_PRODUCT_ID,
    )

    # 3. Record issue
    issue = service.record_issue(
        issue_id=DEMO_ISSUE_ID,
        product_id=DEMO_PRODUCT_ID,
        title=DEMO_ISSUE_TITLE,
        description="SSO and email reset tokens fail to authenticate against cloud auth API.",
        category="authentication",
        severity="high",
    )

    # 4. Open support ticket (unresolved)
    ticket = service.open_support_ticket(
        ticket_id=DEMO_TICKET_ID,
        customer_id=DEMO_CUSTOMER_ID,
        product_id=DEMO_PRODUCT_ID,
        issue_id=DEMO_ISSUE_ID,
        title=DEMO_TICKET_TITLE,
        description=DEMO_TICKET_DESC,
        priority="high",
    )

    # 5. Record troubleshooting step 1 (FAILED outcome)
    step1 = service.record_troubleshooting_step(
        ticket_id=DEMO_TICKET_ID,
        step_number=1,
        action="Dispatched automated password reset link to user's registered email",
        outcome=TroubleshootingOutcome.FAILED,
        notes="Reset token expired immediately on load; user received HTTP 401 Unauthorized.",
        step_id=DEMO_STEP_1_ID,
    )

    # 6. Conversation 1: Initial report and failed resolution attempt
    conv1 = service.start_conversation(
        customer_id=DEMO_CUSTOMER_ID,
        channel="ai_chat",
        conversation_id=DEMO_CONV_1_ID,
    )
    service.add_message(
        conversation_id=conv1.id,
        sender_type="customer",
        content="Hi, I can't log in to my SmartMesh admin dashboard. It keeps giving me an error.",
        ticket_id=DEMO_TICKET_ID,
        authorized_customer_id=DEMO_CUSTOMER_ID,
    )
    service.add_message(
        conversation_id=conv1.id,
        sender_type="assistant",
        content=(
            "Hello Sarah! I see you're having trouble logging into your SmartMesh Gateway Pro. "
            f"I have opened ticket {DEMO_TICKET_ID} for you and sent a password reset link. "
            "Please try using that link to reset your credentials."
        ),
        ticket_id=DEMO_TICKET_ID,
        authorized_customer_id=DEMO_CUSTOMER_ID,
    )
    service.add_message(
        conversation_id=conv1.id,
        sender_type="customer",
        content=(
            "I clicked the link right away, but it says 'Token expired (HTTP 401)'. It didn't work."
        ),
        ticket_id=DEMO_TICKET_ID,
        authorized_customer_id=DEMO_CUSTOMER_ID,
    )
    service.add_message(
        conversation_id=conv1.id,
        sender_type="assistant",
        content=(
            "I understand. I recorded that the password reset link failed due to immediate "
            f"token expiration. Your ticket {DEMO_TICKET_ID} remains open while we investigate."
        ),
        ticket_id=DEMO_TICKET_ID,
        authorized_customer_id=DEMO_CUSTOMER_ID,
    )

    # 7. Pre-create empty Conversation 2 for the follow-up session
    conv2 = service.start_conversation(
        customer_id=DEMO_CUSTOMER_ID,
        channel="ai_chat",
        conversation_id=DEMO_CONV_2_ID,
    )

    summary = {
        "customer": {"id": customer.id, "name": customer.name, "email": customer.email},
        "product": {"id": product.id, "name": product.name, "sku": product.sku},
        "issue": {"id": issue.id, "title": issue.title},
        "ticket": {"id": ticket.id, "title": ticket.title, "status": ticket.status.value},
        "troubleshooting_step": {
            "id": step1.id,
            "action": step1.action,
            "outcome": step1.outcome.value,
        },
        "conversations": [conv1.id, conv2.id],
    }
    logger.info("Hackathon demo successfully seeded: %s", summary)
    return summary


def clear_hackathon_demo(service: SupportService) -> int:
    """Safely delete ONLY entities created with the 'demo-' prefix.

    Args:
        service: Active application SupportService.

    Returns:
        Number of demo nodes deleted.

    Raises:
        GraphSupportError: If deletion fails.
    """
    logger.info("Cleaning up hackathon demo records (id STARTS WITH 'demo-')...")
    driver_manager = service.customer_repo.driver_manager
    database = service.customer_repo.database

    cypher = """
    MATCH (n)
    WHERE n.id STARTS WITH 'demo-'
    DETACH DELETE n
    RETURN count(n) AS deleted_count
    """
    try:
        with driver_manager.session(database=database) as session:
            result = session.run(cypher)
            record = result.single()
            deleted_count = record["deleted_count"] if record else 0
            logger.info("Safely deleted %d hackathon demo nodes.", deleted_count)
            return deleted_count
    except Exception as err:
        logger.error("Failed to clear demo data: %s", err)
        raise GraphSupportError(f"Failed to clear demo data: {err}") from err
