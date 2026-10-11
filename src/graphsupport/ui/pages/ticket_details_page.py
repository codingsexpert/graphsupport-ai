"""Ticket Details operations page for GraphSupport AI (Phase 6).

Displays multi-hop ticket graph context: customer, product, issue, troubleshooting timeline,
attempt outcomes (FAILED, SUCCESS, PARTIAL, UNKNOWN), verified resolutions, and status transitions.
"""

import logging

import streamlit as st

from graphsupport.application.support_service import SupportService
from graphsupport.config.settings import Settings
from graphsupport.graph.driver import get_driver_manager
from graphsupport.graph.models import TicketStatus, TroubleshootingOutcome

logger = logging.getLogger("graphsupport.ui.pages.ticket_details")


def _get_service(settings: Settings) -> SupportService | None:
    if not settings.is_neo4j_configured:
        return None
    try:
        dm = get_driver_manager()
        return SupportService(driver_manager=dm, database=settings.neo4j_database)
    except Exception as err:
        logger.error("Failed to initialize SupportService: %s", err)
        return None


def render_ticket_details_page(settings: Settings) -> None:
    """Render the comprehensive ticket details and troubleshooting timeline view."""
    st.subheader("🔍 Ticket 360 & Diagnostic Timeline")
    st.caption(
        "Inspect ticket graph topology, diagnostic troubleshooting attempts, "
        "outcome fidelity, verified resolutions, and workflow transitions."
    )

    service = _get_service(settings)
    if not service:
        st.warning("⚠️ **Neo4j is not connected.** Ticket details are disabled.")
        return

    # Select / Lookup Ticket
    sel_ticket_id = st.session_state.get("selected_ticket_id", "")
    ticket_id_input = st.text_input(
        "Enter or Paste Ticket ID", value=sel_ticket_id, key="tkt_det_id_input"
    )

    if not ticket_id_input.strip():
        st.info("ℹ️ Please enter a Ticket ID above or select one from the Tickets queue.")
        return

    tid = ticket_id_input.strip()
    try:
        details = service.get_ticket_details(tid)
    except Exception as err:
        st.error(f"Failed to load ticket details: {err}")
        return

    if not details:
        st.error(f"❌ Ticket with ID `{tid}` was not found in Neo4j.")
        return

    ticket = details.ticket
    customer = details.customer
    product = details.product
    issue = details.issue
    steps = details.troubleshooting_steps
    resolutions = details.resolutions

    # Ticket Header Card
    status_icon = (
        "🟢"
        if ticket.status.value == "resolved"
        else "🔵"
        if ticket.status.value == "in_progress"
        else "⚪"
        if ticket.status.value == "closed"
        else "🟡"
    )

    with st.container(border=True):
        st.markdown(f"### {status_icon} {ticket.title}")
        stat_val = ticket.status.value.upper()
        prio_val = ticket.priority.upper()
        st.caption(f"Ticket ID: `{ticket.id}` | Priority: `{prio_val}` | Status: `{stat_val}`")
        st.markdown(f"**Description**: {ticket.description}")
        c_time = ticket.created_at.strftime("%Y-%m-%d %H:%M")
        u_time = ticket.updated_at.strftime("%Y-%m-%d %H:%M")
        st.caption(f"Created: {c_time} UTC | Updated: {u_time} UTC")

    # Connected Graph Entities
    c_col1, c_col2, c_col3 = st.columns(3)
    with c_col1:
        with st.container(border=True):
            st.markdown("##### 👤 Customer")
            if customer:
                st.markdown(f"**{customer.name}**")
                st.caption(f"ID: `{customer.id}`\nTier: `{customer.tier.upper()}`")
            else:
                st.caption("No linked customer.")

    with c_col2:
        with st.container(border=True):
            st.markdown("##### 📦 Affected Product")
            if product:
                st.markdown(f"**{product.name}**")
                st.caption(f"SKU: `{product.sku}` | Ver: `{product.version}`")
            else:
                st.caption("No linked product.")

    with c_col3:
        with st.container(border=True):
            st.markdown("##### ⚠️ Tracked Defect / Issue")
            if issue:
                st.markdown(f"**{issue.title}**")
                st.caption(f"ID: `{issue.id}` | Sev: `{issue.severity.upper()}`")
            else:
                st.caption("No canonical issue linked.")

    st.divider()

    # Workflow Status Transition
    st.markdown("#### 🔄 Workflow Status Transition")
    tr_col1, tr_col2 = st.columns([2, 1])
    with tr_col1:
        status_options = [s.value for s in TicketStatus]
        current_idx = status_options.index(ticket.status.value)
        target_status = st.selectbox(
            "Change Status to:",
            options=status_options,
            index=current_idx,
            format_func=lambda x: x.upper(),
            key="sel_target_status",
        )
    with tr_col2:
        confirm_transition = st.checkbox("Confirm status transition", key="chk_confirm_status")
        if st.button("Apply Status Change", use_container_width=True, key="btn_apply_status"):
            if not confirm_transition:
                st.warning("⚠️ Please check 'Confirm status transition' first.")
            elif target_status == ticket.status.value:
                st.info("Status is already set to this value.")
            else:
                try:
                    updated = service.transition_ticket_status(ticket.id, target_status)
                    st.success(f"✅ Ticket transitioned to `{updated.status.value.upper()}`")
                    st.session_state.pop("cached_overview_metrics", None)
                    st.rerun()
                except Exception as err:
                    st.error(f"❌ Failed to update status: {err}")

    st.divider()

    # Troubleshooting Timeline
    st.markdown("#### 🔧 Diagnostic Troubleshooting Timeline")
    if not steps:
        st.info("ℹ️ No troubleshooting attempts logged yet for this ticket.")
    else:
        for step in steps:
            outcome_badge = (
                "🟢 SUCCESS"
                if step.outcome.value == "success"
                else "🔴 FAILED"
                if step.outcome.value == "failed"
                else "🟡 PARTIAL"
                if step.outcome.value == "partial"
                else "⚪ UNKNOWN"
            )
            with st.container(border=True):
                st.markdown(f"**Step {step.step_number}: {step.action}** — `{outcome_badge}`")
                time_str = step.executed_at.strftime("%Y-%m-%d %H:%M UTC")
                f_str = f" | Follows: `{step.previous_step_id}`" if step.previous_step_id else ""
                st.caption(f"Attempt: `{step.id}` | Executed: {time_str}{f_str}")
                if step.notes:
                    st.markdown(f"> *Notes*: {step.notes}")

    # Add Troubleshooting Step Form
    with st.expander("➕ Log New Diagnostic Troubleshooting Attempt"):
        with st.form("form_log_step", clear_on_submit=True):
            next_step_num = len(steps) + 1
            s_num = st.number_input("Step Number", min_value=1, value=next_step_num)
            s_act = st.text_input(
                "Diagnostic Action Executed", placeholder="Re-pair Zigbee channel 15"
            )
            s_out = st.selectbox(
                "Observed Outcome",
                options=["failed", "success", "partial", "unknown"],
                format_func=lambda x: x.upper(),
            )
            s_notes = st.text_area(
                "Diagnostic Notes / Observations",
                placeholder="Gateway responded with error code 0x4B...",
            )
            prev_step_options = ["None"] + [s.id for s in steps]
            s_prev = st.selectbox("Previous Step Chained", options=prev_step_options)
            s_submit = st.form_submit_button("Record Diagnostic Step", use_container_width=True)

            if s_submit:
                if not s_act.strip():
                    st.error("Action is required.")
                else:
                    prev_id = None if s_prev == "None" else s_prev
                    try:
                        recorded = service.record_troubleshooting_step(
                            ticket_id=ticket.id,
                            step_number=int(s_num),
                            action=s_act.strip(),
                            outcome=TroubleshootingOutcome(s_out),
                            notes=s_notes.strip(),
                            previous_step_id=prev_id,
                        )
                        out_lbl = recorded.outcome.value.upper()
                        st.success(
                            f"✅ Step {recorded.step_number} recorded with outcome `{out_lbl}`"
                        )
                        st.session_state.pop("cached_overview_metrics", None)
                        st.rerun()
                    except Exception as err:
                        st.error(f"❌ Failed to record step: {err}")

    st.divider()

    # Resolutions
    st.markdown("#### 🏆 Verified Resolutions")
    if not resolutions:
        st.info("ℹ️ No verified resolutions recorded yet.")
    else:
        for res in resolutions:
            with st.container(border=True):
                st.markdown(f"**Verified Fix**: {res.summary}")
                r_dt = res.created_at.strftime("%Y-%m-%d")
                st.caption(f"ID: `{res.id}` | Type: {res.resolution_type} | {r_dt}")

    # Add Resolution Form
    with st.expander("➕ Record Verified Ticket Resolution"):
        with st.form("form_record_resolution", clear_on_submit=True):
            r_sum = st.text_area(
                "Resolution Summary",
                placeholder="Downgraded gateway firmware to v1.2.0 which resolved WiFi dropouts.",
            )
            r_type = st.selectbox(
                "Resolution Type",
                options=["fix", "workaround", "hardware_replacement", "configuration_change"],
            )
            r_ver = st.checkbox("Verified by Customer or Field Engineer", value=True)
            r_submit = st.form_submit_button("Save Resolution", use_container_width=True)

            if r_submit:
                if not r_sum.strip():
                    st.error("Resolution summary is required.")
                else:
                    try:
                        res = service.record_ticket_resolution(
                            ticket_id=ticket.id,
                            summary=r_sum.strip(),
                            resolution_type=r_type,
                            verified=r_ver,
                        )
                        st.success(f"✅ Resolution saved (ID: `{res.id}`)")
                        st.session_state.pop("cached_overview_metrics", None)
                        st.rerun()
                    except Exception as err:
                        st.error(f"❌ Failed to record resolution: {err}")
