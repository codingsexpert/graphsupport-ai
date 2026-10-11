"""Sidebar and navigation components for GraphSupport AI (Phase 6).

Provides page routing across all 10 operations sections:
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
    "📊 Overview",
    "💬 Support Chat",
    "👥 Customers",
    "📦 Products",
    "🎫 Tickets",
    "🔍 Ticket Details",
    "📜 Conversation History",
    "🕸️ Graph Explorer",
    "🩺 System Health",
    "📈 Evaluation",
]


def render_sidebar(settings: Settings, health: HealthStatus) -> str:
    """Render the application sidebar and return the selected navigation page."""
    with st.sidebar:
        st.markdown(f"## 🕸️ {settings.app_name}")
        st.caption(f"v{settings.app_version} • {settings.app_env.value.title()} Operations")

        st.divider()

        if "nav_page" not in st.session_state:
            st.session_state["nav_page"] = NAV_OPTIONS[0]

        # In case nav_page was set to something outside options
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

        st.markdown("### System Readiness")
        if not health.neo4j.configured:
            neo4j_txt = "Not Configured"
        elif health.neo4j.reachability == "reachable":
            neo4j_txt = "🟢 Connected"
        elif health.neo4j.reachability == "unavailable":
            neo4j_txt = "🔴 Unavailable"
        else:
            neo4j_txt = "🟡 Configured"
        st.markdown(f"- **Neo4j**: {neo4j_txt}")

        llm_label = (
            f"🟢 {settings.llm_provider.value.title()}"
            if settings.is_llm_configured
            else "🟡 Mock Mode"
        )
        st.markdown(f"- **AI Agent**: {llm_label}")
        st.markdown("- **Active Phase**: `Phase 6: Dashboard`")

        st.divider()
        st.caption(f"Platform: {health.platform_info} | UTC: {health.timestamp[:19]}")

    return st.session_state["nav_page"]
