"""Application coordination service for GraphSupport AI.

Coordinates domain workflows, transaction boundaries, input validation,
and authorization guards across customer, product, ticket, conversation,
troubleshooting, and resolution operations.
"""

import logging
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from graphsupport.core.exceptions import (
    AuthorizationError,
    EntityNotFoundError,
    ValidationError,
)
from graphsupport.graph.driver import Neo4jDriverManager, get_driver_manager
from graphsupport.graph.models import (
    Conversation,
    ConversationDetails,
    Customer,
    Issue,
    Message,
    Product,
    Resolution,
    SupportTicket,
    TicketDetails,
    TicketStatus,
    TroubleshootingOutcome,
    TroubleshootingStep,
)
from graphsupport.graph.repositories.conversation_repo import ConversationRepository
from graphsupport.graph.repositories.customer_repo import CustomerRepository
from graphsupport.graph.repositories.product_repo import ProductRepository
from graphsupport.graph.repositories.ticket_repo import TicketRepository
from graphsupport.graph.repositories.troubleshooting_repo import TroubleshootingRepository

logger = logging.getLogger("graphsupport.application.support_service")

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
VALID_SENDER_TYPES = {"customer", "agent", "system", "assistant"}
VALID_SEVERITIES = {"low", "medium", "high", "critical"}
VALID_PRIORITIES = {"low", "medium", "high", "urgent"}
VALID_TIERS = {"free", "standard", "pro", "enterprise"}


class SupportService:
    """High-level application coordinator managing customer support graph operations.

    Ensures domain validation before persistence, maintains cross-entity consistency,
    and enforces tenant/customer authorization context boundaries.
    """

    def __init__(
        self,
        driver_manager: Neo4jDriverManager | None = None,
        database: str | None = None,
        customer_repo: CustomerRepository | None = None,
        product_repo: ProductRepository | None = None,
        ticket_repo: TicketRepository | None = None,
        conversation_repo: ConversationRepository | None = None,
        troubleshooting_repo: TroubleshootingRepository | None = None,
    ) -> None:
        self.driver_manager = driver_manager or get_driver_manager()
        self.database = database or self.driver_manager.settings.neo4j_database

        self.customer_repo = customer_repo or CustomerRepository(
            driver_manager=self.driver_manager, database=self.database
        )
        self.product_repo = product_repo or ProductRepository(
            driver_manager=self.driver_manager, database=self.database
        )
        self.ticket_repo = ticket_repo or TicketRepository(
            driver_manager=self.driver_manager, database=self.database
        )
        self.conversation_repo = conversation_repo or ConversationRepository(
            driver_manager=self.driver_manager, database=self.database
        )
        self.troubleshooting_repo = troubleshooting_repo or TroubleshootingRepository(
            driver_manager=self.driver_manager, database=self.database
        )

    # =========================================================================
    # Customer Operations
    # =========================================================================

    def register_customer(
        self,
        email: str,
        name: str,
        customer_id: str | None = None,
        tier: str = "standard",
        metadata: dict[str, Any] | None = None,
    ) -> Customer:
        """Register a new customer with a stable application-generated ID.

        Args:
            email: Validated customer email address.
            name: Customer display or legal name.
            customer_id: Optional stable customer ID; generated if omitted.
            tier: Service level tier ('free', 'standard', 'pro', 'enterprise').
            metadata: Optional non-sensitive customer attributes.

        Returns:
            Persisted Customer entity.

        Raises:
            ValidationError: If input validation fails.
            DuplicateEntityError: If customer ID or email already exists.
        """
        clean_email = email.strip().lower()
        if not EMAIL_REGEX.match(clean_email):
            raise ValidationError(f"Invalid email format: '{email}'")

        clean_name = name.strip()
        if not clean_name or len(clean_name) > 120:
            raise ValidationError("Customer name must be between 1 and 120 characters")

        clean_tier = tier.strip().lower()
        if clean_tier not in VALID_TIERS:
            raise ValidationError(
                f"Invalid customer tier '{tier}'. Must be one of: {sorted(VALID_TIERS)}"
            )

        cid = (customer_id or f"cust-{uuid.uuid4().hex[:12]}").strip()
        if not cid:
            raise ValidationError("Customer ID cannot be empty")

        customer = Customer(
            id=cid,
            email=clean_email,
            name=clean_name,
            tier=clean_tier,
            created_at=datetime.now(UTC),
            metadata=metadata or {},
        )
        logger.info("Registering customer: id=%s, email=%s", customer.id, customer.email)
        return self.customer_repo.create_customer(customer)

    def get_customer(self, customer_id: str) -> Customer | None:
        """Retrieve a customer by unique identifier."""
        clean_id = customer_id.strip()
        if not clean_id:
            raise ValidationError("Customer ID cannot be empty")
        return self.customer_repo.get_by_id(clean_id)

    def update_customer_profile(
        self,
        customer_id: str,
        name: str | None = None,
        tier: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Customer:
        """Update explicitly permitted customer fields without altering identity."""
        clean_id = customer_id.strip()
        if not clean_id:
            raise ValidationError("Customer ID cannot be empty")

        clean_name = name.strip() if name is not None else None
        if clean_name is not None and (len(clean_name) == 0 or len(clean_name) > 120):
            raise ValidationError("Customer name must be between 1 and 120 characters")

        clean_tier = tier.strip().lower() if tier is not None else None
        if clean_tier is not None and clean_tier not in VALID_TIERS:
            raise ValidationError(
                f"Invalid customer tier '{tier}'. Must be one of: {sorted(VALID_TIERS)}"
            )

        return self.customer_repo.update_customer(
            customer_id=clean_id,
            name=clean_name,
            tier=clean_tier,
            metadata=metadata,
        )

    def list_customers(self, limit: int = 50, skip: int = 0) -> list[Customer]:
        """List customers with pagination and deterministic ordering."""
        return self.customer_repo.list_customers(limit=limit, skip=skip)

    # =========================================================================
    # Product Operations
    # =========================================================================

    def register_or_update_product(
        self,
        name: str,
        sku: str,
        product_id: str | None = None,
        category: str = "general",
        version: str = "1.0.0",
        metadata: dict[str, Any] | None = None,
    ) -> Product:
        """Register or update a product with idempotent upsert semantics."""
        clean_name = name.strip()
        if not clean_name or len(clean_name) > 150:
            raise ValidationError("Product name must be between 1 and 150 characters")

        clean_sku = sku.strip().upper()
        if not clean_sku or len(clean_sku) > 64:
            raise ValidationError("Product SKU must be between 1 and 64 characters")

        clean_category = category.strip().lower() or "general"
        clean_version = version.strip() or "1.0.0"

        pid = (product_id or f"prod-{clean_sku.lower()}").strip()
        if not pid:
            raise ValidationError("Product ID cannot be empty")

        product = Product(
            id=pid,
            name=clean_name,
            sku=clean_sku,
            category=clean_category,
            version=clean_version,
            metadata=metadata or {},
        )
        logger.info("Upserting product: id=%s, sku=%s", product.id, product.sku)
        return self.product_repo.upsert_product(product)

    def get_product(self, product_id: str) -> Product | None:
        """Retrieve a product by ID."""
        clean_id = product_id.strip()
        if not clean_id:
            raise ValidationError("Product ID cannot be empty")
        return self.product_repo.get_by_id(clean_id)

    def list_products(self, limit: int = 50, skip: int = 0) -> list[Product]:
        """List all products with pagination."""
        return self.product_repo.list_products(limit=limit, skip=skip)

    def associate_customer_with_product(self, customer_id: str, product_id: str) -> bool:
        """Link customer to product via (:Customer)-[:USES]->(:Product)."""
        cid = customer_id.strip()
        pid = product_id.strip()
        if not cid or not pid:
            raise ValidationError("Customer ID and Product ID cannot be empty")
        return self.product_repo.link_customer_to_product(customer_id=cid, product_id=pid)

    def get_customer_products(self, customer_id: str) -> list[Product]:
        """Retrieve all products used by a customer."""
        cid = customer_id.strip()
        if not cid:
            raise ValidationError("Customer ID cannot be empty")
        return self.product_repo.get_customer_products(cid)

    # =========================================================================
    # Issue and Ticket Operations
    # =========================================================================

    def record_issue(
        self,
        product_id: str,
        title: str,
        description: str,
        category: str = "bug",
        severity: str = "medium",
        issue_id: str | None = None,
    ) -> Issue:
        """Create a known Issue associated with a Product."""
        pid = product_id.strip()
        if not pid:
            raise ValidationError("Product ID cannot be empty")

        clean_title = title.strip()
        if not clean_title or len(clean_title) > 200:
            raise ValidationError("Issue title must be between 1 and 200 characters")

        clean_desc = description.strip()
        if not clean_desc or len(clean_desc) > 3000:
            raise ValidationError("Issue description must be between 1 and 3000 characters")

        clean_severity = severity.strip().lower()
        if clean_severity not in VALID_SEVERITIES:
            raise ValidationError(
                f"Invalid severity '{severity}'. Must be one of: {sorted(VALID_SEVERITIES)}"
            )

        iid = (issue_id or f"iss-{uuid.uuid4().hex[:12]}").strip()
        issue = Issue(
            id=iid,
            title=clean_title,
            description=clean_desc,
            category=category.strip().lower() or "general",
            severity=clean_severity,
            created_at=datetime.now(UTC),
            product_id=pid,
        )
        return self.ticket_repo.create_issue(issue=issue, product_id=pid)

    def open_support_ticket(
        self,
        customer_id: str,
        product_id: str,
        title: str,
        description: str,
        priority: str = "medium",
        issue_id: str | None = None,
        ticket_id: str | None = None,
    ) -> SupportTicket:
        """Atomically create a SupportTicket linked to Customer, Product, and optional Issue."""
        cid = customer_id.strip()
        pid = product_id.strip()
        if not cid or not pid:
            raise ValidationError("Customer ID and Product ID are required")

        clean_title = title.strip()
        if not clean_title or len(clean_title) > 200:
            raise ValidationError("Ticket title must be between 1 and 200 characters")

        clean_desc = description.strip()
        if not clean_desc or len(clean_desc) > 3000:
            raise ValidationError("Ticket description must be between 1 and 3000 characters")

        clean_priority = priority.strip().lower()
        if clean_priority not in VALID_PRIORITIES:
            raise ValidationError(
                f"Invalid priority '{priority}'. Must be one of: {sorted(VALID_PRIORITIES)}"
            )

        tid = (ticket_id or f"tkt-{uuid.uuid4().hex[:12]}").strip()
        ticket = SupportTicket(
            id=tid,
            title=clean_title,
            description=clean_desc,
            status=TicketStatus.OPEN,
            priority=clean_priority,
            created_at=datetime.now(UTC),
            customer_id=cid,
            product_id=pid,
            issue_id=issue_id.strip() if issue_id else None,
        )
        logger.info("Opening support ticket: id=%s, customer=%s", ticket.id, cid)
        return self.ticket_repo.create_ticket(
            ticket=ticket,
            customer_id=cid,
            product_id=pid,
            issue_id=issue_id.strip() if issue_id else None,
        )

    def get_ticket(self, ticket_id: str) -> SupportTicket | None:
        """Retrieve a ticket by ID."""
        tid = ticket_id.strip()
        if not tid:
            raise ValidationError("Ticket ID cannot be empty")
        return self.ticket_repo.get_by_id(tid)

    def get_ticket_details(self, ticket_id: str) -> TicketDetails | None:
        """Retrieve full ticket details with customer, product, issue, and history."""
        tid = ticket_id.strip()
        if not tid:
            raise ValidationError("Ticket ID cannot be empty")
        return self.ticket_repo.get_ticket_details(tid)

    def transition_ticket_status(
        self,
        ticket_id: str,
        new_status: TicketStatus | str,
    ) -> SupportTicket:
        """Update ticket status via validated domain status enum."""
        tid = ticket_id.strip()
        if not tid:
            raise ValidationError("Ticket ID cannot be empty")

        if isinstance(new_status, str):
            try:
                status_enum = TicketStatus(new_status.strip().lower())
            except ValueError as err:
                valid = [s.value for s in TicketStatus]
                raise ValidationError(
                    f"Invalid ticket status '{new_status}'. Allowed values: {valid}"
                ) from err
        else:
            status_enum = new_status

        logger.info("Transitioning ticket %s to status: %s", tid, status_enum.value)
        return self.ticket_repo.update_ticket_status(ticket_id=tid, new_status=status_enum)

    def list_customer_tickets(
        self,
        customer_id: str,
        status: TicketStatus | str | None = None,
        limit: int = 50,
        skip: int = 0,
    ) -> list[SupportTicket]:
        """List tickets belonging to a customer with optional status filter."""
        cid = customer_id.strip()
        if not cid:
            raise ValidationError("Customer ID cannot be empty")

        status_enum: TicketStatus | None = None
        if status is not None:
            if isinstance(status, str):
                try:
                    status_enum = TicketStatus(status.strip().lower())
                except ValueError as err:
                    valid = [s.value for s in TicketStatus]
                    raise ValidationError(
                        f"Invalid ticket status filter '{status}'. Allowed values: {valid}"
                    ) from err
            else:
                status_enum = status

        return self.ticket_repo.list_customer_tickets(
            customer_id=cid, status=status_enum, limit=limit, skip=skip
        )

    # =========================================================================
    # Conversation and Message Operations
    # =========================================================================

    def start_conversation(
        self,
        customer_id: str,
        channel: str = "chat",
        session_id: str | None = None,
        conversation_id: str | None = None,
    ) -> Conversation:
        """Start a new Conversation linked to a valid Customer."""
        cid = customer_id.strip()
        if not cid:
            raise ValidationError("Customer ID cannot be empty")

        customer = self.customer_repo.get_by_id(cid)
        if not customer:
            raise EntityNotFoundError(f"Customer with ID '{cid}' does not exist")

        conv_id = (conversation_id or f"conv-{uuid.uuid4().hex[:12]}").strip()
        sess_id = (session_id or f"sess-{uuid.uuid4().hex[:8]}").strip()

        conv = Conversation(
            id=conv_id,
            session_id=sess_id,
            channel=channel.strip().lower() or "chat",
            started_at=datetime.now(UTC),
            status="active",
            customer_id=cid,
        )
        logger.info("Starting conversation: id=%s for customer=%s", conv.id, cid)
        return self.conversation_repo.create_conversation(conv, customer_id=cid)

    def list_customer_conversations(
        self,
        customer_id: str,
        limit: int = 50,
        skip: int = 0,
    ) -> list[Conversation]:
        """List all conversations for a customer."""
        cid = customer_id.strip()
        if not cid:
            raise ValidationError("Customer ID cannot be empty")
        return self.conversation_repo.list_customer_conversations(
            customer_id=cid, limit=limit, skip=skip
        )

    def add_message(
        self,
        conversation_id: str,
        sender_type: str,
        content: str,
        sequence_number: int | None = None,
        ticket_id: str | None = None,
        message_id: str | None = None,
        authorized_customer_id: str | None = None,
    ) -> Message:
        """Append a message to a conversation with authorization boundary verification.

        Args:
            conversation_id: Target conversation UUID.
            sender_type: Message role ('customer', 'agent', 'system', 'assistant').
            content: Validated text content (up to 4000 chars).
            sequence_number: Optional explicit sequence number; auto-computed if omitted.
            ticket_id: Optional support ticket to link via (:Message)-[:ABOUT]->(:SupportTicket).
            message_id: Optional stable message ID; generated if omitted.
            authorized_customer_id: Customer identity boundary token. If provided,
                verifies conversation belongs to this customer.

        Raises:
            ValidationError: If role or content length is invalid.
            EntityNotFoundError: If conversation or ticket not found.
            AuthorizationError: If conversation does not belong to authorized_customer_id.
        """
        conv_id = conversation_id.strip()
        if not conv_id:
            raise ValidationError("Conversation ID cannot be empty")

        clean_sender = sender_type.strip().lower()
        if clean_sender not in VALID_SENDER_TYPES:
            raise ValidationError(
                f"Invalid sender_type '{sender_type}'. Must be one of: {sorted(VALID_SENDER_TYPES)}"
            )

        clean_content = content.strip()
        if not clean_content or len(clean_content) > 4000:
            raise ValidationError("Message content must be between 1 and 4000 characters")

        # Identity boundary verification
        conversation = self.conversation_repo.get_by_id(conv_id)
        if not conversation:
            raise EntityNotFoundError(f"Conversation with ID '{conv_id}' does not exist")

        if authorized_customer_id is not None:
            clean_auth_id = authorized_customer_id.strip()
            if conversation.customer_id != clean_auth_id:
                raise AuthorizationError(
                    f"Customer '{clean_auth_id}' is not authorized to access "
                    f"conversation '{conv_id}'"
                )

        # Auto-compute next sequence number if not explicitly specified
        seq = sequence_number
        if seq is None:
            existing = self.conversation_repo.get_conversation_messages(conv_id)
            seq = (max((m.sequence_number for m in existing), default=0)) + 1

        mid = (message_id or f"msg-{uuid.uuid4().hex[:12]}").strip()
        msg = Message(
            id=mid,
            sender_type=clean_sender,
            content=clean_content,
            sequence_number=seq,
            timestamp=datetime.now(UTC),
            conversation_id=conv_id,
            ticket_id=ticket_id.strip() if ticket_id else None,
        )
        return self.conversation_repo.append_message(
            message=msg,
            conversation_id=conv_id,
            ticket_id=ticket_id.strip() if ticket_id else None,
        )

    def get_conversation_details(
        self,
        conversation_id: str,
        authorized_customer_id: str | None = None,
    ) -> ConversationDetails | None:
        """Retrieve conversation metadata and messages, checking authorization if provided."""
        conv_id = conversation_id.strip()
        if not conv_id:
            raise ValidationError("Conversation ID cannot be empty")

        details = self.conversation_repo.get_conversation_details(conv_id)
        if not details:
            return None

        if authorized_customer_id is not None:
            clean_auth_id = authorized_customer_id.strip()
            if details.conversation.customer_id != clean_auth_id:
                raise AuthorizationError(
                    f"Customer '{clean_auth_id}' is not authorized to view conversation '{conv_id}'"
                )

        return details

    # =========================================================================
    # Troubleshooting Attempts and Resolutions
    # =========================================================================

    def record_troubleshooting_step(
        self,
        ticket_id: str,
        step_number: int,
        action: str,
        outcome: TroubleshootingOutcome | str,
        notes: str = "",
        previous_step_id: str | None = None,
        step_id: str | None = None,
    ) -> TroubleshootingStep:
        """Record a troubleshooting step linked to a ticket and optionally chain follow-up."""
        tid = ticket_id.strip()
        if not tid:
            raise ValidationError("Ticket ID cannot be empty")

        if step_number < 1:
            raise ValidationError(f"Step number must be >= 1, got {step_number}")

        clean_action = action.strip()
        if not clean_action or len(clean_action) > 500:
            raise ValidationError("Step action must be between 1 and 500 characters")

        if isinstance(outcome, str):
            try:
                outcome_enum = TroubleshootingOutcome(outcome.strip().lower())
            except ValueError as err:
                valid = [o.value for o in TroubleshootingOutcome]
                raise ValidationError(
                    f"Invalid troubleshooting outcome '{outcome}'. Allowed values: {valid}"
                ) from err
        else:
            outcome_enum = outcome

        sid = (step_id or f"step-{uuid.uuid4().hex[:12]}").strip()
        step = TroubleshootingStep(
            id=sid,
            step_number=step_number,
            action=clean_action,
            outcome=outcome_enum,
            notes=notes.strip() if notes else "",
            executed_at=datetime.now(UTC),
            ticket_id=tid,
            previous_step_id=previous_step_id.strip() if previous_step_id else None,
        )
        logger.info("Recording step %s for ticket %s: outcome=%s", sid, tid, outcome_enum.value)
        return self.troubleshooting_repo.record_step(
            step=step,
            ticket_id=tid,
            previous_step_id=previous_step_id.strip() if previous_step_id else None,
        )

    def get_troubleshooting_attempts(self, ticket_id: str) -> list[TroubleshootingStep]:
        """Retrieve all troubleshooting steps for a ticket in chronological order."""
        tid = ticket_id.strip()
        if not tid:
            raise ValidationError("Ticket ID cannot be empty")
        return self.troubleshooting_repo.get_ticket_attempts(tid)

    def record_ticket_resolution(
        self,
        ticket_id: str,
        summary: str,
        resolution_type: str = "fix",
        verified: bool = True,
        resolution_id: str | None = None,
    ) -> Resolution:
        """Record an explicit resolution linked via [:HAS_RESOLUTION]."""
        tid = ticket_id.strip()
        if not tid:
            raise ValidationError("Ticket ID cannot be empty")

        clean_summary = summary.strip()
        if not clean_summary or len(clean_summary) > 2000:
            raise ValidationError("Resolution summary must be between 1 and 2000 characters")

        rid = (resolution_id or f"res-{uuid.uuid4().hex[:12]}").strip()
        resolution = Resolution(
            id=rid,
            summary=clean_summary,
            resolution_type=resolution_type.strip().lower() or "fix",
            verified=verified,
            created_at=datetime.now(UTC),
            ticket_id=tid,
        )
        logger.info("Recording resolution %s for ticket %s", rid, tid)
        return self.troubleshooting_repo.record_resolution(resolution=resolution, ticket_id=tid)

    def get_ticket_resolutions(self, ticket_id: str) -> list[Resolution]:
        """Retrieve all resolutions recorded for a ticket."""
        tid = ticket_id.strip()
        if not tid:
            raise ValidationError("Ticket ID cannot be empty")
        return self.troubleshooting_repo.get_ticket_resolutions(tid)
