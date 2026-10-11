"""Overview dashboard page for GraphSupport AI.

Displays high-level KPI metrics, real-time graph telemetry, recent tickets,
and troubleshooting attempts with clean, professional enterprise styling.
"""

import logging
from typing import Any

import streamlit as st

from graphsupport.application.demo_seed import (
    clear_hackathon_demo,
    is_hackathon_demo_seeded,
    seed_hackathon_demo,
)
from graphsupport.application.support_service import SupportService
from graphsupport.config.settings import Settings
from graphsupport.graph.driver import get_driver_manager

logger = logging.getLogger("graphsupport.ui.pages.overview")


def _get_service(settings: Settings) -> SupportService | None:
    """Safely obtain SupportService instance if Neo4j is configured."""
    if not settings.is_neo4j_configured:
        return None
    try:
        dm = get_driver_manager()
        return SupportService(driver_manager=dm, database=settings.neo4j_database)
    except Exception as err:
        logger.error("Failed to initialize SupportService: %s", err)
        return None


def render_overview_page(settings: Settings) -> None:
    """Render the operations overview dashboard."""
    top_col1, top_col2 = st.columns([3, 1])
    with top_col1:
        st.subheader("Support Operations Overview")
        st.caption(
            "Live graph telemetry across customers, products, tickets, diagnostic steps, "
            "and verified resolutions."
        )
    with top_col2:
        if st.button("Refresh Telemetry", use_container_width=True):
            st.session_state.pop("cached_overview_metrics", None)
            st.rerun()

    service = _get_service(settings)
    if not service:
        st.warning(
            "Neo4j is not connected. Operational metrics cannot be retrieved from the "
            "database. Please verify your credentials or visit the System Health page."
        )
        return

    # Demo Quick-Action Panel
    demo_seeded = is_hackathon_demo_seeded(service)
    demo_c1, demo_c2 = st.columns([3, 1])
    with demo_c1:
        if demo_seeded:
            st.success(
                "Demo Persona Active: **Sarah Chen** (`demo-cust-sarah`) with Ticket "
                "**demo-tkt-101** and recorded failed password reset attempt."
            )
        else:
            st.info(
                "Demo Scenario Ready: Load the 2-session memory demo "
                "(Sarah Chen, SmartMesh Gateway, failed reset attempt) with 1 click."
            )
    with demo_c2:
        if demo_seeded:
            if st.button("Reset Demo Data", use_container_width=True, key="btn_reset_demo"):
                count = clear_hackathon_demo(service)
                st.session_state.pop("cached_overview_metrics", None)
                st.toast(f"Safely removed {count} demo records")
                st.rerun()
        else:
            if st.button("Load Demo Scenario", use_container_width=True, key="btn_seed_demo"):
                seed_hackathon_demo(service)
                st.session_state.pop("cached_overview_metrics", None)
                st.toast("Seeded demo scenario successfully")
                st.rerun()

    # Fetch real metrics
    metrics: dict[str, Any] | None = st.session_state.get("cached_overview_metrics")
    if metrics is None:
        try:
            with st.spinner("Computing live knowledge graph metrics..."):
                metrics = service.get_overview_metrics()
                st.session_state["cached_overview_metrics"] = metrics
        except Exception as err:
            st.error(f"Failed to load graph metrics: {err}")
            return

    # Metric Cards Row 1: Totals
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric(label="Customers", value=metrics["total_customers"])
    with c2:
        st.metric(label="Products", value=metrics["total_products"])
    with c3:
        st.metric(label="Support Tickets", value=metrics["total_tickets"])
    with c4:
        raw_p = getattr(settings.llm_provider, "value", settings.llm_provider) or "Mock"
        st.metric(
            label="AI Provider",
            value=str(raw_p).title(),
            delta="Configured" if settings.is_llm_configured else "Mock Mode",
        )

    # Metric Cards Row 2: Ticket Status Breakdown
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        st.metric(label="Open", value=metrics["open_tickets"])
    with s2:
        st.metric(label="In Progress", value=metrics["in_progress_tickets"])
    with s3:
        st.metric(label="Resolved", value=metrics["resolved_tickets"])
    with s4:
        st.metric(label="Closed", value=metrics["closed_tickets"])

    st.divider()

    # Recent Activity Columns
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.markdown("### Recent Support Tickets")
        recent_tickets = metrics.get("recent_tickets", [])
        if not recent_tickets:
            st.info("No support tickets recorded yet.")
        else:
            for t in recent_tickets:
                status_text = t.status.value.replace("_", " ").upper()
                with st.container(border=True):
                    head_c1, head_c2 = st.columns([3, 1])
                    with head_c1:
                        st.markdown(f"**{t.title}**")
                        st.caption(
                            f"ID: `{t.id}` | Priority: `{t.priority.upper()}` "
                            f"| Status: `{status_text}`"
                        )
                    with head_c2:
                        if st.button("Details", key=f"ov_tkt_{t.id}", use_container_width=True):
                            st.session_state["selected_ticket_id"] = t.id
                            st.session_state["nav_page"] = "Ticket Details"
                            st.rerun()

    with col_right:
        st.markdown("### Recent Troubleshooting Attempts")
        recent_steps = metrics.get("recent_steps", [])
        if not recent_steps:
            st.info("No troubleshooting attempts logged yet.")
        else:
            for s in recent_steps:
                outcome_text = s.outcome.value.upper()
                with st.container(border=True):
                    st.markdown(f"**Step {s.step_number}: {s.action}** — `{outcome_text}`")
                    time_str = s.executed_at.strftime("%Y-%m-%d %H:%M UTC")
                    st.caption(f"Ticket ID: `{s.ticket_id}` | Time: {time_str}")
                    if s.notes:
                        st.caption(f"Notes: {s.notes}")

    st.divider()

    # Recent Resolutions
    st.markdown("### Recent Verified Resolutions")
    recent_res = metrics.get("recent_resolutions", [])
    if not recent_res:
        st.info("No verified resolutions recorded yet.")
    else:
        for r in recent_res:
            with st.container(border=True):
                st.markdown(f"**Verified Fix**: {r.summary}")
                r_date = r.created_at.strftime("%Y-%m-%d")
                st.caption(f"Ticket: `{r.ticket_id}` | Type: {r.resolution_type} | {r_date}")
