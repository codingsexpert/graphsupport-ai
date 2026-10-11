"""Reusable Streamlit UI components for GraphSupport AI.

Renders status cards, architecture overview, phase indicators, and safe configuration details.
"""

from typing import Any

import streamlit as st

from graphsupport.config.settings import Settings
from graphsupport.core.health import HealthStatus


def render_header(title: str, subtitle: str, phase_name: str) -> None:
    """Render the application hero section."""
    st.markdown(
        f"""
        <div class="gs-hero-badge">Stage: {phase_name}</div>
        <div class="gs-title">{title}</div>
        <div class="gs-subtitle">{subtitle}</div>
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
        neo4j_pill = (
            '<span class="gs-pill-success">Configured</span>'
            if health.neo4j.configured
            else '<span class="gs-pill-neutral">Phase 2 Reserved</span>'
        )
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
        - **UI Layer (`graphsupport.ui`)**: Declarative Streamlit dashboard components
          and token-based styling.
        - **Graph Persistence (Phase 2)**: Native Neo4j property graph holding customer
          support context (users, tickets, devices, resolutions).
        - **Reasoning & Agent Engine (Phase 5)**: Context-aware LLM agent retrieving subgraphs
          to resolve support inquiries with cross-session memory.
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
            "Active",
            "Modular architecture, typed settings, structured logging, health check, and tests.",
            True,
        ),
        (
            "Phase 2: Neo4j Schema & Storage",
            "Upcoming",
            "Neo4j driver connection, property graph constraints, schemas, and repositories.",
            False,
        ),
        (
            "Phase 3: Knowledge & Ticket Ingestion",
            "Pending",
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
            else '<span class="gs-pill-neutral">UPCOMING</span>'
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
