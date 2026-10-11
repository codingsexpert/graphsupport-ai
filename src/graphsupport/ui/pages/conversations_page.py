"""Conversation History operations page for GraphSupport AI (Phase 6).

Inspects multi-session support transcripts, message ordering, ticket linkage,
and customer context across historical channels.
"""

import logging

import streamlit as st

from graphsupport.application.support_service import SupportService
from graphsupport.config.settings import Settings
from graphsupport.graph.driver import get_driver_manager

logger = logging.getLogger("graphsupport.ui.pages.conversations")


def _get_service(settings: Settings) -> SupportService | None:
    if not settings.is_neo4j_configured:
        return None
    try:
        dm = get_driver_manager()
        return SupportService(driver_manager=dm, database=settings.neo4j_database)
    except Exception as err:
        logger.error("Failed to initialize SupportService: %s", err)
        return None


def render_conversations_page(settings: Settings) -> None:
    """Render the conversation history and transcript inspection page."""
    st.subheader("Multi-Session Conversation Transcripts")
    st.caption(
        "Audit historical support conversations, inspect chronological message ordering, "
        "and review linked support tickets."
    )

    service = _get_service(settings)
    if not service:
        st.warning("**Neo4j is not connected.** Conversation history is disabled.")
        return

    top_col1, top_col2 = st.columns([3, 1])
    with top_col2:
        page_limit = st.selectbox("Page Size", options=[10, 25, 50], index=0, key="conv_page_size")

    try:
        conversations = service.list_all_conversations(limit=page_limit)
    except Exception as err:
        st.error(f"Failed to fetch conversations: {err}")
        return

    if not conversations:
        st.info("No support conversations found on record.")
        return

    conv_options = {
        f"Session {c.session_id} ({c.started_at.strftime('%Y-%m-%d %H:%M')})": c.id
        for c in conversations
    }

    sel_conv_label = st.selectbox(
        "Select Conversation to View Transcript",
        options=list(conv_options.keys()),
        key="conv_history_sel",
    )
    sel_conv_id = conv_options[sel_conv_label]

    # Conversation Metadata Card
    sel_conv = next((c for c in conversations if c.id == sel_conv_id), None)
    if sel_conv:
        with st.container(border=True):
            m_c1, m_c2, m_c3, m_c4 = st.columns(4)
            m_c1.markdown(f"**Conversation ID**: `{sel_conv.id}`")
            m_c2.markdown(f"**Session**: `{sel_conv.session_id}`")
            m_c3.markdown(f"**Customer**: `{sel_conv.customer_id}`")
            m_c4.markdown(f"**Started**: {sel_conv.started_at.strftime('%Y-%m-%d %H:%M UTC')}")

    st.divider()

    # Message Stream
    messages = service.get_conversation_messages(sel_conv_id)
    if not messages:
        st.info("This conversation session contains no recorded messages.")
        return

    st.markdown(f"#### Messages ({len(messages)} Total)")
    for msg in messages:
        sender_role = "user" if msg.sender_type == "customer" else "assistant"
        with st.chat_message(sender_role):
            header_text = (
                f"**Customer** (`{sel_conv.customer_id if sel_conv else 'customer'}`)"
                if msg.sender_type == "customer"
                else "**GraphSupport AI Agent**"
            )
            time_str = msg.timestamp.strftime("%H:%M:%S UTC")
            ticket_badge = f" | Linked Ticket: `{msg.ticket_id}`" if msg.ticket_id else ""
            st.caption(f"{header_text} • {time_str} • Seq #{msg.sequence_number}{ticket_badge}")
            st.markdown(msg.content)
