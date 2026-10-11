"""Support Chat page for GraphSupport AI (Phase 6).

Integrates the Phase 5 SupportAgent grounded in persistent Neo4j graph memory
and authorized tool execution.
"""

import streamlit as st

from graphsupport.config.settings import Settings
from graphsupport.ui.chat import render_phase5_support_chat


def render_chat_page(settings: Settings) -> None:
    """Render the AI Support Chat operations page."""
    st.subheader("💬 AI Support Agent Workbench")
    st.caption(
        "Direct interactive session with GraphSupport AI. Customer context is automatically "
        "retrieved from Neo4j graph memory, prior troubleshooting attempts are acknowledged, "
        "and authorized diagnostic tools are executed safely."
    )

    st.info(
        "🔒 **Identity Boundary Notice**: The customer selector below represents the current "
        "development and operator identity boundary. In a production enterprise deployment, "
        "this boundary is provided by OAuth 2.0 / OIDC session tokens."
    )

    render_phase5_support_chat(settings)
