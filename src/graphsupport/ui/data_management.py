"""Streamlit data management components for GraphSupport AI (Phase 3).

Provides interactive forms and views for persistent customers, products,
support tickets, conversations, troubleshooting attempts, and resolutions.
All operations execute strictly through the SupportService application layer.
"""

import logging

import streamlit as st

from graphsupport.application import SupportService
from graphsupport.config.settings import Settings
from graphsupport.core.exceptions import (
    AuthorizationError,
    DuplicateEntityError,
    EntityNotFoundError,
    GraphSupportError,
    ValidationError,
)
from graphsupport.graph.driver import get_driver_manager
from graphsupport.graph.models import TicketStatus, TroubleshootingOutcome

logger = logging.getLogger("graphsupport.ui.data_management")


def _get_service(settings: Settings) -> SupportService | None:
    """Retrieve or initialize the application SupportService if Neo4j is configured."""
    if not settings.is_neo4j_configured:
        return None
    try:
        dm = get_driver_manager()
        return SupportService(driver_manager=dm, database=settings.neo4j_database)
    except Exception as err:
        logger.error("Failed to initialize SupportService: %s", err)
        return None


def render_phase3_data_management(settings: Settings) -> None:
    """Render the Phase 3 Data Management workbench in Streamlit."""
    st.subheader("Phase 3: Persistent Customer Support Workbench")
    st.markdown(
        """
        Interactive management of customers, products, support tickets, conversations,
        and troubleshooting workflows backed by the Neo4j knowledge graph.
        """
    )

    service = _get_service(settings)
    if not service:
        st.warning(
            "⚠️ **Neo4j is not connected or credentials are not configured.** "
            "Data operations are disabled until a valid Neo4j connection is established. "
            "Verify your settings in the control panel above."
        )
        return

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "Customers",
            "Products",
            "Tickets & Issues",
            "Conversations",
            "Troubleshooting & Resolutions",
        ]
    )

    with tab1:
        _render_customer_management(service)

    with tab2:
        _render_product_management(service)

    with tab3:
        _render_ticket_management(service)

    with tab4:
        _render_conversation_management(service)

    with tab5:
        _render_troubleshooting_management(service)


def _render_customer_management(service: SupportService) -> None:
    """Render Customer registration, profile updating, and listing."""
    st.markdown("### Customer Management")
    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("#### Register New Customer")
        with st.form("register_customer_form", clear_on_submit=True):
            email = st.text_input("Email Address*", placeholder="customer@example.com")
            name = st.text_input("Full Name*", placeholder="Jane Doe")
            tier = st.selectbox("Support Tier", ["standard", "pro", "enterprise", "free"])
            custom_id = st.text_input(
                "Custom ID (optional)",
                placeholder="cust-custom-001",
                help="Leave empty for auto-generated ID",
            )
            submitted = st.form_submit_button("Register Customer", use_container_width=True)

            if submitted:
                if not email or not name:
                    st.error("Email and Name are required fields.")
                else:
                    try:
                        with st.spinner("Persisting customer to graph..."):
                            customer = service.register_customer(
                                email=email,
                                name=name,
                                tier=tier,
                                customer_id=custom_id or None,
                            )
                        st.success(f"Customer registered successfully! ID: `{customer.id}`")
                    except DuplicateEntityError as err:
                        st.error(f"Duplicate Error: {err.message}")
                    except ValidationError as err:
                        st.error(f"Validation Error: {err.message}")
                    except GraphSupportError as err:
                        st.error(f"Persistence Error: {err.message}")
                    except Exception as err:
                        st.error(f"An unexpected error occurred: {err}")

    with col2:
        st.markdown("#### Customer Lookup & Update")
        lookup_id = st.text_input("Lookup Customer by ID", placeholder="cust-12345")
        if st.button("Search Customer", key="btn_lookup_cust", use_container_width=True):
            if not lookup_id:
                st.error("Please provide a Customer ID to lookup.")
            else:
                try:
                    with st.spinner("Querying graph..."):
                        c = service.get_customer(lookup_id)
                    if c:
                        st.success(f"Found customer: **{c.name}** ({c.email})")
                        st.json(
                            {
                                "id": c.id,
                                "name": c.name,
                                "email": c.email,
                                "tier": c.tier,
                                "created_at": c.created_at.isoformat(),
                            }
                        )
                    else:
                        st.info(f"No customer found with ID `{lookup_id}`.")
                except Exception as err:
                    st.error(f"Lookup failed: {err}")

    st.markdown("---")
    st.markdown("#### Registered Customers")
    try:
        customers = service.list_customers(limit=25, skip=0)
        if customers:
            customer_rows = [
                {
                    "ID": c.id,
                    "Name": c.name,
                    "Email": c.email,
                    "Tier": c.tier.upper(),
                    "Created": c.created_at.strftime("%Y-%m-%d %H:%M"),
                }
                for c in customers
            ]
            st.dataframe(customer_rows, use_container_width=True)
        else:
            st.info("No customers found in database. Register one above!")
    except Exception as err:
        st.error(f"Failed to fetch customer list: {err}")


def _render_product_management(service: SupportService) -> None:
    """Render Product registration and Customer-Product linkage."""
    st.markdown("### Product Catalog & Customer Usage")
    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("#### Register / Upsert Product")
        with st.form("upsert_product_form", clear_on_submit=True):
            p_name = st.text_input("Product Name*", placeholder="Cloud Analytics Suite")
            p_sku = st.text_input("SKU / Product Code*", placeholder="CAS-ENTERPRISE-V2")
            p_cat = st.text_input("Category", value="saas")
            p_ver = st.text_input("Version", value="2.1.0")
            submitted = st.form_submit_button("Save Product", use_container_width=True)

            if submitted:
                if not p_name or not p_sku:
                    st.error("Product Name and SKU are required.")
                else:
                    try:
                        with st.spinner("Upserting product in graph..."):
                            prod = service.register_or_update_product(
                                name=p_name,
                                sku=p_sku,
                                category=p_cat,
                                version=p_ver,
                            )
                        st.success(f"Product saved! ID: `{prod.id}`, SKU: `{prod.sku}`")
                    except Exception as err:
                        st.error(f"Failed to save product: {err}")

    with col2:
        st.markdown("#### Link Customer to Product (`[:USES]`)")
        with st.form("link_cust_prod_form", clear_on_submit=True):
            link_cid = st.text_input("Customer ID*", placeholder="cust-12345")
            link_pid = st.text_input("Product ID*", placeholder="prod-cas-enterprise-v2")
            link_sub = st.form_submit_button("Establish Link (:USES)", use_container_width=True)

            if link_sub:
                if not link_cid or not link_pid:
                    st.error("Both Customer ID and Product ID are required.")
                else:
                    try:
                        with st.spinner("Creating [:USES] relationship..."):
                            service.associate_customer_with_product(link_cid, link_pid)
                        st.success(
                            f"Linked customer `{link_cid}` to product `{link_pid}` successfully!"
                        )
                    except EntityNotFoundError as err:
                        st.error(f"Entity Not Found: {err.message}")
                    except Exception as err:
                        st.error(f"Link failed: {err}")

    st.markdown("---")
    st.markdown("#### Product Catalog")
    try:
        products = service.list_products(limit=25, skip=0)
        if products:
            prod_rows = [
                {
                    "ID": p.id,
                    "Name": p.name,
                    "SKU": p.sku,
                    "Category": p.category,
                    "Version": p.version,
                }
                for p in products
            ]
            st.dataframe(prod_rows, use_container_width=True)
        else:
            st.info("No products found in database.")
    except Exception as err:
        st.error(f"Failed to fetch products: {err}")


def _render_ticket_management(service: SupportService) -> None:
    """Render Support Ticket creation, Issue registration, and detail views."""
    st.markdown("### Support Tickets & Issues")
    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("#### Open Support Ticket")
        with st.form("open_ticket_form", clear_on_submit=True):
            t_cid = st.text_input("Customer ID*", placeholder="cust-12345")
            t_pid = st.text_input("Product ID*", placeholder="prod-cas-enterprise-v2")
            t_title = st.text_input("Ticket Title*", placeholder="API gateway connection timeout")
            t_desc = st.text_area(
                "Description*",
                placeholder="Receiving 504 Gateway Timeout when executing queries...",
            )
            t_prio = st.selectbox("Priority", ["medium", "high", "urgent", "low"])
            t_issue_id = st.text_input(
                "Associated Issue ID (optional)",
                placeholder="iss-gateway-timeout",
            )
            t_sub = st.form_submit_button("Create Ticket", use_container_width=True)

            if t_sub:
                if not t_cid or not t_pid or not t_title or not t_desc:
                    st.error("Customer ID, Product ID, Title, and Description are required.")
                else:
                    try:
                        with st.spinner("Opening ticket and linking graph nodes..."):
                            ticket = service.open_support_ticket(
                                customer_id=t_cid,
                                product_id=t_pid,
                                title=t_title,
                                description=t_desc,
                                priority=t_prio,
                                issue_id=t_issue_id or None,
                            )
                        st.success(f"Ticket opened successfully! ID: `{ticket.id}`")
                    except EntityNotFoundError as err:
                        st.error(f"Referenced entity missing: {err.message}")
                    except Exception as err:
                        st.error(f"Failed to open ticket: {err}")

    with col2:
        st.markdown("#### Register Known Issue for Product")
        with st.form("create_issue_form", clear_on_submit=True):
            iss_pid = st.text_input("Product ID*", placeholder="prod-cas-enterprise-v2")
            iss_title = st.text_input("Issue Title*", placeholder="504 Gateway Timeout")
            iss_desc = st.text_area("Issue Description*", placeholder="Connection pool exhausts...")
            iss_cat = st.text_input("Category", value="performance")
            iss_sev = st.selectbox("Severity", ["medium", "high", "critical", "low"])
            iss_sub = st.form_submit_button("Register Issue", use_container_width=True)

            if iss_sub:
                if not iss_pid or not iss_title or not iss_desc:
                    st.error("Product ID, Title, and Description are required.")
                else:
                    try:
                        with st.spinner("Registering issue and linking to product..."):
                            issue = service.record_issue(
                                product_id=iss_pid,
                                title=iss_title,
                                description=iss_desc,
                                category=iss_cat,
                                severity=iss_sev,
                            )
                        st.success(f"Issue registered! ID: `{issue.id}`")
                    except EntityNotFoundError as err:
                        st.error(f"Product not found: {err.message}")
                    except Exception as err:
                        st.error(f"Failed to register issue: {err}")

    st.markdown("---")
    st.markdown("#### Ticket Details & Status Transitions")
    col_t1, col_t2 = st.columns([1, 1])
    with col_t1:
        inspect_tid = st.text_input("Inspect Ticket by ID", placeholder="tkt-12345")
        if st.button("Fetch Ticket Details", use_container_width=True):
            if not inspect_tid:
                st.error("Ticket ID is required.")
            else:
                try:
                    with st.spinner("Traversing ticket graph..."):
                        details = service.get_ticket_details(inspect_tid)
                    if details:
                        st.session_state["active_ticket_details"] = details
                    else:
                        st.info(f"No ticket found with ID `{inspect_tid}`.")
                except Exception as err:
                    st.error(f"Error fetching ticket: {err}")

    active_details = st.session_state.get("active_ticket_details")
    if active_details:
        t = active_details.ticket
        st.markdown(
            f"**Ticket `{t.id}`**: *{t.title}* | Status: **{t.status.value.upper()}** | "
            f"Priority: **{t.priority.upper()}**"
        )
        if active_details.customer:
            st.markdown(
                f"- **Customer**: {active_details.customer.name} (`{active_details.customer.id}`)"
            )
        if active_details.product:
            p_name = active_details.product.name
            p_sku = active_details.product.sku
            st.markdown(f"- **Product**: {p_name} (SKU: `{p_sku}`)")
        if active_details.issue:
            i_title = active_details.issue.title
            i_sev = active_details.issue.severity
            st.markdown(f"- **Issue**: {i_title} (Severity: `{i_sev}`)")

        with col_t2:
            st.markdown("##### Update Ticket Status")
            new_st = st.selectbox(
                "New Status",
                [s.value for s in TicketStatus],
                index=[s.value for s in TicketStatus].index(t.status.value),
            )
            if st.button("Apply Status Change", use_container_width=True):
                try:
                    updated = service.transition_ticket_status(t.id, new_st)
                    st.success(f"Ticket status updated to `{updated.status.value}`")
                    # Refresh active ticket details
                    st.session_state["active_ticket_details"] = service.get_ticket_details(t.id)
                    st.rerun()
                except Exception as err:
                    st.error(f"Failed to update status: {err}")


def _render_conversation_management(service: SupportService) -> None:
    """Render Conversation session management and sequential message persistence."""
    st.markdown("### Conversation & Message Persistence")
    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("#### Start Conversation Session")
        with st.form("start_conv_form", clear_on_submit=True):
            conv_cid = st.text_input("Customer ID*", placeholder="cust-12345")
            conv_channel = st.selectbox("Channel", ["chat", "web", "email", "api"])
            conv_sub = st.form_submit_button("Start Conversation", use_container_width=True)

            if conv_sub:
                if not conv_cid:
                    st.error("Customer ID is required.")
                else:
                    try:
                        with st.spinner("Creating conversation session..."):
                            conv = service.start_conversation(
                                customer_id=conv_cid,
                                channel=conv_channel,
                            )
                        st.success(f"Conversation started! ID: `{conv.id}`")
                    except EntityNotFoundError as err:
                        st.error(f"Customer not found: {err.message}")
                    except Exception as err:
                        st.error(f"Failed to start conversation: {err}")

    with col2:
        st.markdown("#### Append Message to Conversation")
        with st.form("append_msg_form", clear_on_submit=True):
            msg_conv_id = st.text_input("Conversation ID*", placeholder="conv-12345")
            msg_sender = st.selectbox("Sender Type*", ["customer", "agent", "assistant", "system"])
            msg_content = st.text_area(
                "Message Content*", placeholder="Hello, I need assistance..."
            )
            msg_tkt_id = st.text_input("Ticket Reference (optional)", placeholder="tkt-12345")
            msg_auth_cid = st.text_input(
                "Demo Auth Boundary: Customer ID (optional)",
                placeholder="cust-12345",
                help="If provided, validates customer ownership of the conversation.",
            )
            msg_sub = st.form_submit_button("Append Message", use_container_width=True)

            if msg_sub:
                if not msg_conv_id or not msg_content:
                    st.error("Conversation ID and Message Content are required.")
                else:
                    try:
                        with st.spinner("Appending message to graph..."):
                            m = service.add_message(
                                conversation_id=msg_conv_id,
                                sender_type=msg_sender,
                                content=msg_content,
                                ticket_id=msg_tkt_id or None,
                                authorized_customer_id=msg_auth_cid or None,
                            )
                        st.success(
                            f"Message appended! ID: `{m.id}` (Sequence: #{m.sequence_number})"
                        )
                    except AuthorizationError as err:
                        st.error(f"Authorization Error: {err.message}")
                    except EntityNotFoundError as err:
                        st.error(f"Entity Not Found: {err.message}")
                    except Exception as err:
                        st.error(f"Failed to append message: {err}")

    st.markdown("---")
    st.markdown("#### View Conversation Transcript")
    view_conv_id = st.text_input("Load Conversation ID", placeholder="conv-12345")
    if st.button("Load Messages", use_container_width=True):
        if not view_conv_id:
            st.error("Please enter a Conversation ID.")
        else:
            try:
                with st.spinner("Fetching transcript..."):
                    details = service.get_conversation_details(view_conv_id)
                if details:
                    st.markdown(
                        f"**Conversation `{details.conversation.id}`** | "
                        f"Customer: `{details.conversation.customer_id}` | "
                        f"Channel: `{details.conversation.channel}` | "
                        f"Total Messages: **{len(details.messages)}**"
                    )
                    for m in details.messages:
                        tkt_label = f" (About: `{m.ticket_id}`)" if m.ticket_id else ""
                        st.markdown(
                            f"> **[#{m.sequence_number}] {m.sender_type.upper()}{tkt_label}** "
                            f"*{m.timestamp.strftime('%H:%M:%S')}*:\n"
                            f"> {m.content}"
                        )
                else:
                    st.info(f"No conversation found with ID `{view_conv_id}`.")
            except Exception as err:
                st.error(f"Failed to load transcript: {err}")


def _render_troubleshooting_management(service: SupportService) -> None:
    """Render Troubleshooting steps and Resolution management."""
    st.markdown("### Troubleshooting Steps & Resolutions")
    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("#### Record Troubleshooting Step")
        with st.form("record_step_form", clear_on_submit=True):
            s_tid = st.text_input("Ticket ID*", placeholder="tkt-12345")
            s_num = st.number_input("Step Number*", min_value=1, value=1, step=1)
            s_action = st.text_input(
                "Action Taken*", placeholder="Restarted authentication container"
            )
            s_outcome = st.selectbox(
                "Outcome*",
                [o.value for o in TroubleshootingOutcome],
            )
            s_prev_id = st.text_input(
                "Previous Step ID (optional, [:FOLLOWED_BY])",
                placeholder="step-12345",
            )
            s_notes = st.text_area(
                "Notes", placeholder="Container restarted in 12s, error persists."
            )
            s_sub = st.form_submit_button("Record Step", use_container_width=True)

            if s_sub:
                if not s_tid or not s_action:
                    st.error("Ticket ID and Action Taken are required.")
                else:
                    try:
                        with st.spinner("Recording attempt in graph..."):
                            step = service.record_troubleshooting_step(
                                ticket_id=s_tid,
                                step_number=int(s_num),
                                action=s_action,
                                outcome=s_outcome,
                                notes=s_notes,
                                previous_step_id=s_prev_id or None,
                            )
                        st.success(
                            f"Step recorded! ID: `{step.id}` (Outcome: `{step.outcome.value}`)"
                        )
                    except EntityNotFoundError as err:
                        st.error(f"Not Found: {err.message}")
                    except Exception as err:
                        st.error(f"Failed to record step: {err}")

    with col2:
        st.markdown("#### Record Ticket Resolution")
        with st.form("record_resolution_form", clear_on_submit=True):
            r_tid = st.text_input("Ticket ID*", placeholder="tkt-12345")
            r_summary = st.text_area(
                "Resolution Summary*",
                placeholder="Updated connection pool max_size configuration to 50...",
            )
            r_type = st.selectbox(
                "Resolution Type", ["fix", "workaround", "configuration", "patch"]
            )
            r_ver = st.checkbox("Verified with Customer", value=True)
            r_sub = st.form_submit_button("Record Resolution", use_container_width=True)

            if r_sub:
                if not r_tid or not r_summary:
                    st.error("Ticket ID and Resolution Summary are required.")
                else:
                    try:
                        with st.spinner("Persisting resolution..."):
                            res = service.record_ticket_resolution(
                                ticket_id=r_tid,
                                summary=r_summary,
                                resolution_type=r_type,
                                verified=r_ver,
                            )
                        st.success(f"Resolution recorded! ID: `{res.id}`")
                    except EntityNotFoundError as err:
                        st.error(f"Ticket not found: {err.message}")
                    except Exception as err:
                        st.error(f"Failed to record resolution: {err}")

    st.markdown("---")
    st.markdown("#### View Attempts and Resolutions for Ticket")
    hist_tid = st.text_input("Enter Ticket ID to View History", placeholder="tkt-12345")
    if st.button("Fetch Ticket History", use_container_width=True):
        if not hist_tid:
            st.error("Please enter a Ticket ID.")
        else:
            try:
                with st.spinner("Fetching troubleshooting history..."):
                    steps = service.get_troubleshooting_attempts(hist_tid)
                    resolutions = service.get_ticket_resolutions(hist_tid)

                st.markdown(f"##### Attempts for Ticket `{hist_tid}` ({len(steps)} recorded)")
                if steps:
                    for s in steps:
                        prev_txt = (
                            f" *(Followed: `{s.previous_step_id}`)*" if s.previous_step_id else ""
                        )
                        st.markdown(
                            f"- **Step #{s.step_number}** [`{s.outcome.value.upper()}`]{prev_txt}: "
                            f"{s.action} *(Notes: {s.notes or 'None'})*"
                        )
                else:
                    st.info("No troubleshooting attempts recorded for this ticket.")

                st.markdown(
                    f"##### Resolutions for Ticket `{hist_tid}` ({len(resolutions)} recorded)"
                )
                if resolutions:
                    for r in resolutions:
                        ver_txt = "✅ Verified" if r.verified else "⏳ Unverified"
                        st.markdown(
                            f"- **Resolution [{r.resolution_type.upper()}]** ({ver_txt}): "
                            f"{r.summary}"
                        )
                else:
                    st.info("No resolutions recorded for this ticket.")
            except Exception as err:
                st.error(f"Failed to fetch history: {err}")
