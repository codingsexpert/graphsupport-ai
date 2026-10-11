"""Support Chat page for GraphSupport AI.

Integrates the SupportAgent grounded in persistent Neo4j graph memory
and authorized tool execution.
"""

import streamlit as st

from graphsupport.config.settings import Settings
from graphsupport.ui.chat import render_phase5_support_chat


def render_chat_page(settings: Settings) -> None:
    """Render the AI Support Chat operations page."""
    st.subheader("Support Chat Workbench")
    st.caption(
        "Direct conversational session grounded in Neo4j persistent graph memory "
        "and authorized diagnostic tool execution."
    )

    render_phase5_support_chat(settings)
