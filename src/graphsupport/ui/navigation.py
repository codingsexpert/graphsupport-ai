"""Sidebar and navigation components for GraphSupport AI.

Provides clean page routing across operations sections:
1. Overview
2. Support Chat
3. Customers
4. Products
5. Tickets
6. Ticket Details
7. Conversation History
8. Graph Explorer
9. System Health
10. Evaluation
"""

import streamlit as st

from graphsupport.config.settings import Settings
from graphsupport.core.health import HealthStatus

NAV_OPTIONS = [
    "Overview",
    "Support Chat",
    "Customers",
    "Products",
    "Tickets",
    "Ticket Details",
    "Conversation History",
    "Graph Explorer",
    "System Health",
    "Evaluation",
]


def render_sidebar(settings: Settings, health: HealthStatus) -> str:
    """Render the application sidebar and return the selected navigation page."""
    with st.sidebar:
        st.markdown(f"### {settings.app_name}")
        st.caption("AI Support Operations Portal")

        st.divider()

        if "nav_page" not in st.session_state:
            st.session_state["nav_page"] = NAV_OPTIONS[0]

        default_index = 0
        if st.session_state["nav_page"] in NAV_OPTIONS:
            default_index = NAV_OPTIONS.index(st.session_state["nav_page"])

        selected = st.radio(
            "Navigation",
            options=NAV_OPTIONS,
            index=default_index,
            key="sidebar_nav_selection",
            label_visibility="collapsed",
        )

        st.session_state["nav_page"] = selected

        st.divider()

        # Clean System Status
        st.caption("System Status")
        if health.neo4j.reachability == "reachable":
            neo4j_dot = "gs-dot-green"
            neo4j_txt = "Connected"
        elif health.neo4j.configured:
            neo4j_dot = "gs-dot-amber"
            neo4j_txt = "Configured"
        else:
            neo4j_dot = "gs-dot-gray"
            neo4j_txt = "Not Set"

        raw_llm = getattr(settings.llm_provider, "value", settings.llm_provider) or "Mock"
        if settings.is_llm_configured:
            llm_dot = "gs-dot-green"
            llm_txt = str(raw_llm).title()
        else:
            llm_dot = "gs-dot-amber"
            llm_txt = "Mock Mode"

        if settings.is_langsmith_configured:
            ls_dot = "gs-dot-green"
            ls_txt = "LangSmith Active"
        else:
            ls_dot = "gs-dot-gray"
            ls_txt = "Tracing Offline"

        st.markdown(
            f"""
            <div class="gs-sidebar-status">
                <div class="gs-status-item">
                    <span class="gs-dot {neo4j_dot}"></span>
                    <span>Database: {neo4j_txt}</span>
                </div>
                <div class="gs-status-item">
                    <span class="gs-dot {llm_dot}"></span>
                    <span>Provider: {llm_txt}</span>
                </div>
                <div class="gs-status-item">
                    <span class="gs-dot {ls_dot}"></span>
                    <span>{ls_txt}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    return st.session_state["nav_page"]
