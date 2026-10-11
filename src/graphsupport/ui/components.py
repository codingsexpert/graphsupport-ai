"""Reusable Streamlit UI components for GraphSupport AI.

Renders status cards, architecture overview, phase indicators, safe configuration details,
and interactive Neo4j schema/connectivity management.
"""

from typing import Any

import streamlit as st

from graphsupport.config.settings import Settings
from graphsupport.core.health import HealthStatus


def render_header(
    title: str,
    subtitle: str,
    badge: str = "AI Support Intelligence",
    phase_name: str | None = None,
    **kwargs: Any,
) -> None:
    """Render the clean application hero section."""
    display_badge = badge
    if phase_name and badge == "AI Support Intelligence":
        display_badge = phase_name
    st.markdown(
        f"""
        <div class="gs-header-wrapper">
            <span class="gs-hero-badge">{display_badge}</span>
            <div class="gs-title">{title}</div>
            <div class="gs-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_status_cards(health: HealthStatus) -> None:
    """Render high-level application health and subsystem readiness cards."""
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(
            f"""
            <div class="gs-card">
                <div class="gs-card-title">System Status</div>
                <div class="gs-card-value">
                    <span class="gs-pill-success">● {health.status.upper()}</span>
                </div>
                <div class="gs-card-desc">Python {health.python_version}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            f"""
            <div class="gs-card">
                <div class="gs-card-title">Environment</div>
                <div class="gs-card-value">{health.environment.upper()}</div>
                <div class="gs-card-desc">{health.platform_info}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        if not health.neo4j.configured:
            neo4j_pill = '<span class="gs-pill-neutral">Config Missing</span>'
        elif health.neo4j.reachability == "reachable":
            neo4j_pill = '<span class="gs-pill-success">● Connected</span>'
        elif health.neo4j.reachability == "unavailable":
            neo4j_pill = '<span class="gs-pill-warning">● Unavailable</span>'
        else:
            neo4j_pill = '<span class="gs-pill-warning">Not Checked</span>'

        st.markdown(
            f"""
            <div class="gs-card">
                <div class="gs-card-title">Neo4j Graph</div>
                <div class="gs-card-value">{neo4j_pill}</div>
                <div class="gs-card-desc">{health.neo4j.status_message}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col4:
        llm_pill = (
            '<span class="gs-pill-success">Configured</span>'
            if health.llm.configured
            else '<span class="gs-pill-neutral">Phase 5 Reserved</span>'
        )
        st.markdown(
            f"""
            <div class="gs-card">
                <div class="gs-card-title">LLM Provider</div>
                <div class="gs-card-value">{llm_pill}</div>
                <div class="gs-card-desc">{health.llm.status_message}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_database_control_panel(settings: Settings) -> None:
    """Render interactive controls for Neo4j connectivity and schema verification."""
    st.subheader("Neo4j Database Operations (Phase 2)")

    if not settings.is_neo4j_configured:
        st.info(
            "Neo4j connection parameters are not fully configured. "
            "Please configure NEO4J_URI, NEO4J_USERNAME, and NEO4J_PASSWORD in your .env file."
        )
        return

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Verify Live Connection", use_container_width=True):
            with st.spinner("Connecting to Neo4j..."):
                try:
                    from graphsupport.graph.driver import get_driver_manager

                    dm = get_driver_manager(settings=settings)
                    dm.verify_connectivity()
                    srv = dm.get_server_info()
                    agent = srv.get("agent", "Neo4j")
                    st.success(f"Successfully connected to Neo4j! Server Agent: {agent}")
                except Exception as err:
                    st.error(f"Connection verification failed: {type(err).__name__}: {err}")

    with col2:
        if st.button("Initialize Graph Schema (Idempotent)", use_container_width=True):
            with st.spinner("Applying constraints and indexes..."):
                try:
                    from graphsupport.graph.driver import get_driver_manager
                    from graphsupport.graph.schema import initialize_schema

                    dm = get_driver_manager(settings=settings)
                    report = initialize_schema(dm.get_driver(), database=settings.neo4j_database)
                    if report.is_successful:
                        msg = (
                            f"Schema initialization successful! Applied "
                            f"{report.succeeded}/{report.total} constraints & indexes."
                        )
                        st.success(msg)
                    else:
                        st.warning(
                            f"Applied {report.succeeded}/{report.total} statements. "
                            f"{report.failed} encountered issues."
                        )
                except Exception as err:
                    st.error(f"Schema initialization failed: {type(err).__name__}: {err}")


def render_architecture_overview() -> None:
    """Render the architectural diagram and component boundaries."""
    st.subheader("Architectural Foundation")
    st.markdown(
        """
        GraphSupport AI employs a modular layered design with strict boundary isolation:

        - **Config Layer (`graphsupport.config`)**: Typed environment configuration via
          Pydantic Settings with automatic secret masking.
        - **Core Layer (`graphsupport.core`)**: Centralized exception hierarchy,
          structured logging, and health readiness monitoring.
        - **Graph Persistence (`graphsupport.graph`)**: Managed Neo4j driver connection pooling,
          idempotent schema constraints/indexes, and parameterized entity repositories.
        - **Domain Models (`graphsupport.graph.models`)**: Pydantic entities for Customer, Product,
          Issue, SupportTicket, Conversation, Message, TroubleshootingStep, and Resolution.
        - **UI Layer (`graphsupport.ui`)**: Declarative Streamlit dashboard components
          and token-based styling.
        """
    )


def render_safe_config_section(settings: Settings) -> None:
    """Render non-sensitive configuration parameters safely in an expandable container."""
    with st.expander("Safe Configuration Inspection", expanded=False):
        st.markdown(
            "Below is the loaded runtime configuration. Sensitive values like passwords "
            "and API keys are completely masked to prevent credential exposure."
        )
        summary: dict[str, Any] = settings.safe_summary()
        st.json(summary)


def render_phase_roadmap() -> None:
    """Render the phased project implementation roadmap."""
    st.subheader("Phased Implementation Roadmap")

    phases = [
        (
            "Phase 1: Professional Foundation",
            "Completed",
            "Modular architecture, typed settings, structured logging, health check, and tests.",
            False,
        ),
        (
            "Phase 2: Neo4j Schema & Storage",
            "Active",
            "Neo4j driver connection, property graph constraints, schemas, and repositories.",
            True,
        ),
        (
            "Phase 3: Knowledge & Ticket Ingestion",
            "Upcoming",
            "Support ticket parsing, customer identity linkage, and resolution ingestion.",
            False,
        ),
        (
            "Phase 4: Context Retrieval & Graph Algorithms",
            "Pending",
            "Multi-hop graph traversal, subgraph extraction, and troubleshooting lookup.",
            False,
        ),
        (
            "Phase 5: Context-Aware LLM Support Agent",
            "Pending",
            "Graph-augmented LLM reasoning, cross-session memory, and structured responses.",
            False,
        ),
        (
            "Phase 6: Interactive Support Interface",
            "Pending",
            "Interactive chat UI, customer context explorer, and graph visualization.",
            False,
        ),
    ]

    for title, _badge, desc, is_active in phases:
        badge_html = (
            '<span class="gs-pill-success">CURRENT</span>'
            if is_active
            else '<span class="gs-pill-neutral">MILESTONE</span>'
        )
        active_class = "active" if is_active else ""
        st.markdown(
            f"""
            <div class="gs-phase-item {active_class}">
                <div class="gs-phase-title">{title} &nbsp; {badge_html}</div>
                <div class="gs-phase-desc">{desc}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
