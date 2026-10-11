"""Support Tickets dashboard page for GraphSupport AI.

Provides ticket directory, status filtering, search, quick ticket creation,
and links to the dedicated Ticket Details view.
"""

import logging

import streamlit as st

from graphsupport.application.support_service import SupportService
from graphsupport.config.settings import Settings
from graphsupport.core.exceptions import ValidationError
from graphsupport.graph.driver import get_driver_manager
from graphsupport.graph.models import TicketStatus

logger = logging.getLogger("graphsupport.ui.pages.tickets")


def _get_service(settings: Settings) -> SupportService | None:
    if not settings.is_neo4j_configured:
        return None
    try:
        dm = get_driver_manager()
        return SupportService(driver_manager=dm, database=settings.neo4j_database)
    except Exception as err:
        logger.error("Failed to initialize SupportService: %s", err)
        return None


def render_tickets_page(settings: Settings) -> None:
    """Render the support tickets dashboard page."""
    st.subheader("Support Tickets")
    st.caption(
        "Manage, filter, and track technical support cases linked to customers, "
        "hardware products, and defect classifications."
    )

    service = _get_service(settings)
    if not service:
        st.warning("Neo4j is not connected. Ticket operations are disabled.")
        return

    tab1, tab2 = st.tabs(["Ticket Queue", "Open Ticket"])

    # -------------------------------------------------------------------------
    # TAB 1: Queue & Filtering
    # -------------------------------------------------------------------------
    with tab1:
        f_col1, f_col2, f_col3 = st.columns([2, 1, 1])
        with f_col1:
            search_query = st.text_input("Search Title or Ticket ID", key="tkt_search_kw")
        with f_col2:
            status_filter = st.selectbox(
                "Status Filter",
                options=["All", "Open", "In Progress", "Resolved", "Closed"],
                index=0,
                key="tkt_status_sel",
            )
        with f_col3:
            page_size = st.selectbox(
                "Page Size", options=[10, 25, 50], index=0, key="tkt_page_size"
            )

        filter_enum: TicketStatus | None = None
        if status_filter != "All":
            filter_enum = TicketStatus(status_filter.lower().replace(" ", "_"))

        try:
            tickets = service.list_all_tickets(status=filter_enum, limit=page_size)
        except Exception as err:
            st.error(f"Failed to fetch tickets: {err}")
            return

        if search_query:
            sq = search_query.strip().lower()
            tickets = [t for t in tickets if sq in t.id.lower() or sq in t.title.lower()]

        if not tickets:
            st.info("No support tickets found matching the selected criteria.")
        else:
            for t in tickets:
                status_str = t.status.value.replace("_", " ").upper()
                with st.container(border=True):
                    row_c1, row_c2, row_c3 = st.columns([4, 2, 1])
                    with row_c1:
                        st.markdown(f"**{t.title}**")
                        st.caption(
                            f"ID: `{t.id}` | Customer: `{t.customer_id or 'Unknown'}` | "
                            f"Product: `{t.product_id or 'Unknown'}`"
                        )
                    with row_c2:
                        st.markdown(f"**Status**: `{status_str}`")
                        upd_time = (
                            t.updated_at.strftime("%Y-%m-%d %H:%M") if t.updated_at else "Recently"
                        )
                        st.caption(f"Priority: `{t.priority.upper()}` | Updated: {upd_time}")
                    with row_c3:
                        if st.button("Details", key=f"btn_det_{t.id}", use_container_width=True):
                            st.session_state["selected_ticket_id"] = t.id
                            st.session_state["nav_page"] = "Ticket Details"
                            st.rerun()

    # -------------------------------------------------------------------------
    # TAB 2: Open New Ticket
    # -------------------------------------------------------------------------
    with tab2:
        st.markdown("#### Open Support Ticket")
        try:
            customers = service.list_customers(limit=100)
            products = service.list_products(limit=100)
        except Exception as err:
            st.error(f"Failed to load form prerequisites: {err}")
            return

        if not customers or not products:
            st.warning("At least one customer and product must exist before opening tickets.")
        else:
            cust_dict = {f"{c.name} ({c.id})": c.id for c in customers}
            prod_dict = {f"{p.name} (SKU: {p.sku})": p.id for p in products}

            with st.form("form_open_ticket", clear_on_submit=True):
                t_cust = st.selectbox("Customer", options=list(cust_dict.keys()))
                t_prod = st.selectbox("Affected Product", options=list(prod_dict.keys()))
                t_title = st.text_input(
                    "Ticket Title / Summary", placeholder="Device repeatedly disconnects from WiFi"
                )
                t_desc = st.text_area(
                    "Problem Description",
                    placeholder="Device drops offline every 2 hours after firmware upgrade...",
                )
                t_prio = st.selectbox(
                    "Priority", options=["low", "medium", "high", "urgent"], index=1
                )
                t_submit = st.form_submit_button("Open Support Ticket", use_container_width=True)

                if t_submit:
                    if not t_title.strip() or not t_desc.strip():
                        st.error("Title and Description are required.")
                    else:
                        c_id = cust_dict[t_cust]
                        p_id = prod_dict[t_prod]
                        try:
                            ticket = service.open_support_ticket(
                                customer_id=c_id,
                                product_id=p_id,
                                title=t_title.strip(),
                                description=t_desc.strip(),
                                priority=t_prio,
                            )
                            st.success(f"Ticket opened: **{ticket.title}** (ID: `{ticket.id}`)")
                            st.session_state.pop("cached_overview_metrics", None)
                            st.session_state["selected_ticket_id"] = ticket.id
                        except ValidationError as err:
                            st.warning(f"Validation error: {err}")
                            st.error(f"Failed to open ticket: {err}")
