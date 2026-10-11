"""Streamlit UI component for Phase 4 Graph Memory & Context Inspection.

Allows operators and developers to query customer knowledge subgraphs from Neo4j,
inspect deterministic relevance rankings, review troubleshooting attempt outcomes,
and examine bounded JSON payloads prepared for future AI agent consumption.
All operations execute strictly through the SupportService application layer.
"""

import logging

import streamlit as st

from graphsupport.application import SupportService
from graphsupport.config.settings import Settings
from graphsupport.core.exceptions import (
    AuthorizationError,
    EntityNotFoundError,
    RepositoryError,
    ValidationError,
)
from graphsupport.graph.driver import get_driver_manager
from graphsupport.memory.models import CustomerMemoryContext, RetrievalLimits

logger = logging.getLogger("graphsupport.ui.memory_inspector")


def _get_service(settings: Settings) -> SupportService | None:
    """Retrieve or initialize the application SupportService if Neo4j is configured."""
    if not settings.is_neo4j_configured:
        return None
    try:
        dm = get_driver_manager()
        return SupportService(driver_manager=dm, database=settings.neo4j_database)
    except Exception as err:
        logger.error("Failed to initialize SupportService for Memory Inspector: %s", err)
        return None


def render_phase4_memory_inspector(settings: Settings) -> None:
    """Render the Phase 4 Persistent Graph Memory Inspector dashboard."""
    st.subheader("Phase 4: Persistent Graph Memory & Context Retrieval")
    st.markdown(
        """
        Inspect bounded customer support history and deterministic relevance ranking
        retrieved directly from the Neo4j knowledge graph.
        """
    )

    service = _get_service(settings)
    if not service:
        st.warning(
            "⚠️ **Neo4j is not connected or credentials are not configured.** "
            "Memory retrieval is disabled until a valid Neo4j connection is established. "
            "Verify your settings in the control panel."
        )
        return

    try:
        customers = service.list_customers(limit=50)
    except RepositoryError as err:
        st.error(f"❌ Database error fetching customers: {err}")
        return
    except Exception as err:
        st.error(f"❌ Unexpected error connecting to Neo4j: {err}")
        return

    if not customers:
        st.info(
            "ℹ️ No customers found in the graph. Register a customer above to test memory retrieval."
        )
        return

    # Customer Selection & Optional Filters
    col_cust, col_limits = st.columns([2, 1])
    with col_cust:
        cust_options = {f"{c.name} ({c.email}) [{c.id}]": c for c in customers}
        selected_label = st.selectbox(
            "Select Customer to Inspect Memory*",
            options=list(cust_options.keys()),
            help="All memory retrieval is strictly scoped to this customer's graph boundary.",
        )
        selected_customer = cust_options[selected_label]

    with col_limits:
        max_tickets = st.slider(
            "Max Tickets Limit",
            min_value=1,
            max_value=20,
            value=5,
            help="Upper bound on historical tickets included in the memory context.",
        )

    # Secondary optional filters: products, tickets, issue search
    col_p, col_t, col_q = st.columns([1, 1, 1])

    # Fetch products associated with this customer
    customer_products = service.get_customer_products(selected_customer.id)
    with col_p:
        prod_options = {"All Products": None}
        for p in customer_products:
            prod_options[f"{p.name} ({p.sku})"] = p.id
        selected_prod_label = st.selectbox(
            "Filter by Product (optional)", list(prod_options.keys())
        )
        filter_product_id = prod_options[selected_prod_label]

    # Fetch tickets associated with this customer
    customer_tickets = service.list_customer_tickets(selected_customer.id, limit=25)
    with col_t:
        ticket_options = {"All Tickets": None}
        for t in customer_tickets:
            ticket_options[f"{t.title} [{t.id}] ({t.status.value})"] = t.id
        selected_ticket_label = st.selectbox(
            "Focus on Ticket (optional)", list(ticket_options.keys())
        )
        filter_ticket_id = ticket_options[selected_ticket_label]

    with col_q:
        issue_query = st.text_input(
            "Issue Keywords / Description",
            placeholder="e.g. WiFi connection timeout",
            help="Keyword match boosts relevant tickets and attempts deterministically.",
        )

    # Retrieval Action Button
    retrieve_btn = st.button(
        "Retrieve Customer Graph Memory", type="primary", use_container_width=True
    )

    if retrieve_btn or st.session_state.get("last_inspected_cust") == selected_customer.id:
        st.session_state["last_inspected_cust"] = selected_customer.id

        with st.spinner("Traversing Neo4j customer knowledge subgraph..."):
            try:
                limits = RetrievalLimits(max_tickets=max_tickets)
                context: CustomerMemoryContext = service.retrieve_customer_context(
                    customer_id=selected_customer.id,
                    product_id=filter_product_id,
                    ticket_id=filter_ticket_id,
                    issue_query=issue_query if issue_query.strip() else None,
                    limits=limits,
                )
            except AuthorizationError as err:
                st.error(f"Authorization Error: {err}")
                return
            except EntityNotFoundError as err:
                st.error(f"Not Found: {err}")
                return
            except ValidationError as err:
                st.warning(f"Validation Error: {err}")
                return
            except RepositoryError as err:
                st.error(f"Neo4j Repository Failure: {err}")
                return
            except Exception as err:
                logger.exception("Unexpected error during memory retrieval: %s", err)
                st.error(f"Unexpected Error: {err}")
                return

        # Display Assembled Memory Context
        _render_context_display(context)


def _render_context_display(context: CustomerMemoryContext) -> None:
    """Render the structured CustomerMemoryContext with explanations and outcome badges."""
    meta = context.retrieval_metadata
    st.markdown("---")
    st.markdown(f"### Memory Context for **{context.customer.name}** (`{context.customer.id}`)")

    # Metrics Summary Bar
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Customer Tier", context.customer.tier.upper())
    with m2:
        st.metric("Associated Products", len(context.products))
    with m3:
        st.metric(
            "Ranked Tickets Included", f"{len(context.ranked_tickets)} / {meta.total_tickets_found}"
        )
    with m4:
        st.metric("Retrieval Latency", f"{meta.retrieval_duration_ms:.1f} ms")

    # Missing Information & Warning Indicators
    if context.missing_information:
        st.markdown("##### Missing Information & Diagnostic Flags")
        tags = " ".join([f"`{flag}`" for flag in context.missing_information])
        st.markdown(tags)

    # Empty State Handling
    if not context.ranked_tickets:
        st.info(
            "**No historical support tickets found.** "
            "This customer has no prior ticket history or matching records in Neo4j. "
            "A safe, empty memory structure was returned without synthetic data."
        )
    else:
        st.markdown("#### Ranked Historical Tickets")
        st.caption(
            "Tickets are ranked using explainable criteria: Active status, Explicit ID match, "
            "Product match, Keyword overlap, Recency, and Failed troubleshooting weight."
        )

        for idx, item in enumerate(context.ranked_tickets, 1):
            ticket = item.ticket
            stat_name = ticket.status.value.upper()
            expander_title = (
                f"#{idx} | [{stat_name}] {ticket.title} [`{ticket.id}`] "
                f"— Score: **{item.relevance_score:.1f}**"
            )
            with st.expander(expander_title, expanded=(idx <= 2)):
                # Ticket Metadata & Rationale
                r_col1, r_col2 = st.columns([1, 1])
                with r_col1:
                    st.markdown(
                        f"**Status:** `{ticket.status.value}` | **Priority:** `{ticket.priority}`"
                    )
                    st.markdown(
                        f"**Created:** `{ticket.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}`"
                    )
                    if item.product:
                        st.markdown(f"**Product:** {item.product.name} (`{item.product.sku}`)")
                    if item.issue:
                        st.markdown(
                            f"**Issue Category:** `{item.issue.category}` — {item.issue.summary}"
                        )
                with r_col2:
                    st.markdown("**Deterministic Score Breakdown:**")
                    for factor in item.ranking_reasons:
                        st.markdown(f"- {factor}")

                # Troubleshooting Attempts Section
                st.markdown("##### Previous Troubleshooting Attempts")
                if not item.troubleshooting_attempts:
                    st.caption("No troubleshooting steps recorded for this ticket.")
                else:
                    for att in item.troubleshooting_attempts:
                        outcome_badge = att.outcome.value.upper()
                        st.markdown(
                            f"- Step **{att.step_number}**: {att.action} → `[{outcome_badge}]`"
                        )
                        if att.notes:
                            st.caption(f"  *Notes:* {att.notes}")

                # Resolutions Section
                st.markdown("##### Confirmed Resolutions")
                if not item.resolutions:
                    st.caption("No formal resolutions recorded for this ticket.")
                else:
                    for res in item.resolutions:
                        v_badge = "Verified" if res.verified else "Unverified"
                        st.markdown(
                            f"- **[{res.resolution_type.upper()}]** {res.summary} ({v_badge})"
                        )

    # Active Conversations
    if context.recent_conversations:
        st.markdown("#### Associated Conversations")
        for conv in context.recent_conversations:
            with st.expander(
                f"Conversation `{conv.id}` ({conv.channel}) — {len(conv.messages)} messages"
            ):
                for msg in conv.messages[-5:]:
                    st.markdown(
                        f"**{msg.sender_type.title()}** "
                        f"({msg.timestamp.strftime('%H:%M:%S')}): {msg.content}"
                    )

    # Bounded Serializable JSON Inspector
    with st.expander("View Raw Serializable Context JSON"):
        st.caption(
            "This structured dictionary is serializable and bounded by RetrievalLimits. "
            "In Phase 5, this exact object will be injected into LLM system prompts."
        )
        st.json(context.to_dict())
