"""Customer management operations page for GraphSupport AI.

Provides customer directory, ID search, 360-degree customer context inspection
(products, tickets, conversations), and validated registration forms.
"""

import logging

import streamlit as st

from graphsupport.application.support_service import SupportService
from graphsupport.config.settings import Settings
from graphsupport.core.exceptions import DuplicateEntityError, ValidationError
from graphsupport.graph.driver import get_driver_manager

logger = logging.getLogger("graphsupport.ui.pages.customers")


def _get_service(settings: Settings) -> SupportService | None:
    if not settings.is_neo4j_configured:
        return None
    try:
        dm = get_driver_manager()
        return SupportService(driver_manager=dm, database=settings.neo4j_database)
    except Exception as err:
        logger.error("Failed to initialize SupportService: %s", err)
        return None


def render_customers_page(settings: Settings) -> None:
    """Render the customer management dashboard page."""
    st.subheader("Customer Directory")
    st.caption(
        "Manage registered customers, inspect products, review historical support tickets, "
        "and track multi-session conversation history."
    )

    service = _get_service(settings)
    if not service:
        st.warning("Neo4j is not connected. Customer operations are disabled.")
        return

    tab1, tab2, tab3 = st.tabs(["Directory", "Customer Details", "Register Customer"])

    # -------------------------------------------------------------------------
    # TAB 1: Directory
    # -------------------------------------------------------------------------
    with tab1:
        st.markdown("#### Registered Customers")
        c_col1, c_col2 = st.columns([3, 1])
        with c_col1:
            search_query = st.text_input("Filter by ID or Email", key="cust_search_text")
        with c_col2:
            page_limit = st.selectbox(
                "Page Size", options=[10, 25, 50], index=0, key="cust_page_size"
            )

        try:
            customers = service.list_customers(limit=page_limit)
        except Exception as err:
            st.error(f"Failed to fetch customers: {err}")
            return

        if search_query:
            q = search_query.strip().lower()
            customers = [
                c
                for c in customers
                if q in c.id.lower() or q in c.email.lower() or q in c.name.lower()
            ]

        if not customers:
            st.info("No customers found matching criteria.")
        else:
            table_data = []
            for c in customers:
                table_data.append(
                    {
                        "Customer ID": c.id,
                        "Name": c.name,
                        "Email": c.email,
                        "Tier": c.tier.upper(),
                        "Created At": c.created_at.strftime("%Y-%m-%d %H:%M UTC"),
                    }
                )
            st.dataframe(table_data, use_container_width=True)

            # Quick detail selector
            cust_options = {f"{c.name} ({c.id})": c.id for c in customers}
            sel_label = st.selectbox(
                "Select customer to view details",
                options=list(cust_options.keys()),
                key="cust_quick_sel",
            )
            if st.button("Inspect Selected Customer", key="btn_inspect_cust"):
                st.session_state["selected_customer_id"] = cust_options[sel_label]
                st.rerun()

    # -------------------------------------------------------------------------
    # TAB 2: Details
    # -------------------------------------------------------------------------
    with tab2:
        selected_id = st.session_state.get("selected_customer_id", "")
        lookup_id = st.text_input(
            "Lookup Customer by ID", value=selected_id, key="cust_lookup_input"
        )

        if lookup_id:
            try:
                cust = service.get_customer(lookup_id.strip())
            except ValidationError as err:
                st.warning(f"Validation error: {err}")
                cust = None
            except Exception as err:
                st.error(f"Error fetching customer: {err}")
                cust = None

            if not cust:
                st.error(f"Customer with ID `{lookup_id}` not found.")
            else:
                st.markdown(f"### {cust.name}")
                info_c1, info_c2, info_c3 = st.columns(3)
                info_c1.markdown(f"**ID**: `{cust.id}`")
                info_c2.markdown(f"**Email**: `{cust.email}`")
                info_c3.markdown(f"**Tier**: `{cust.tier.upper()}`")

                st.divider()

                # Products
                st.markdown("#### Associated Products")
                products = service.get_customer_products(cust.id)
                if not products:
                    st.info("No registered products associated with this customer.")
                else:
                    for p in products:
                        st.markdown(f"- **{p.name}** (SKU: `{p.sku}`, Ver: `{p.version}`)")

                # Tickets
                st.markdown("#### Support Tickets")
                tickets = service.list_customer_tickets(cust.id)
                if not tickets:
                    st.info("No support tickets on record for this customer.")
                else:
                    for t in tickets:
                        stat_lbl = t.status.value.replace("_", " ").upper()
                        st.markdown(f"- **{t.title}** (`{t.id}` | `{stat_lbl}`)")

                # Conversations
                st.markdown("#### Support Conversations")
                convs = service.list_customer_conversations(cust.id)
                if not convs:
                    st.info("No conversations on record.")
                else:
                    for cv in convs:
                        c_date = (
                            cv.started_at.strftime("%Y-%m-%d %H:%M") if cv.started_at else "Recent"
                        )
                        st.markdown(
                            f"- **Session `{cv.session_id}`** (ID: `{cv.id}`, Started: {c_date})"
                        )

    # -------------------------------------------------------------------------
    # TAB 3: Register
    # -------------------------------------------------------------------------
    with tab3:
        st.markdown("#### Register Customer")
        with st.form("form_register_customer", clear_on_submit=True):
            r_name = st.text_input("Customer Name", placeholder="Jane Doe")
            r_email = st.text_input("Email Address", placeholder="jane.doe@example.com")
            r_tier = st.selectbox(
                "Service Tier", options=["standard", "pro", "enterprise", "free"], index=0
            )
            submitted = st.form_submit_button("Register Customer", use_container_width=True)

            if submitted:
                if not r_name.strip() or not r_email.strip():
                    st.error("Name and Email are required.")
                else:
                    try:
                        new_c = service.register_customer(
                            name=r_name.strip(),
                            email=r_email.strip(),
                            tier=r_tier,
                        )
                        st.success(f"Registered **{new_c.name}** (ID: `{new_c.id}`)")
                        st.session_state.pop("cached_overview_metrics", None)
                    except DuplicateEntityError as err:
                        st.error(f"Customer already exists: {err}")
                    except ValidationError as err:
                        st.warning(f"Validation error: {err}")
                    except Exception as err:
                        st.error(f"Failed to register: {err}")
