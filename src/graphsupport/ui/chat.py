"""Streamlit UI component for Phase 5 Context-Aware AI Support Chat.

Provides an interactive chat workbench:
- Selects development/demo customer within the authorized boundary.
- Interacts with SupportAgent grounded in persistent Neo4j graph memory.
- Renders conversational messages with clear timestamps and sender badges.
- Displays tool execution badges and audit history.
- Displays helpful configuration state warnings when LLM_API_KEY is not set.
- Executes strictly through application services with zero raw Cypher or provider logic in the UI.
"""

import logging

import streamlit as st

from graphsupport.agents import MockLLMProvider, SupportAgent, get_llm_provider
from graphsupport.application import SupportService
from graphsupport.config.settings import Settings
from graphsupport.core.exceptions import (
    AuthorizationError,
    GraphSupportError,
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMRateLimitError,
    LLMTimeoutError,
    ValidationError,
)
from graphsupport.graph.driver import get_driver_manager

logger = logging.getLogger("graphsupport.ui.chat")


def _get_service(settings: Settings) -> SupportService | None:
    """Retrieve or initialize the application SupportService if Neo4j is configured."""
    if not settings.is_neo4j_configured:
        return None
    try:
        dm = get_driver_manager()
        return SupportService(driver_manager=dm, database=settings.neo4j_database)
    except Exception as err:
        logger.error("Failed to initialize SupportService for Chat: %s", err)
        return None


def render_phase5_support_chat(settings: Settings) -> None:
    """Render the Phase 5 Context-Aware AI Support Chat component."""
    st.subheader("Phase 5: Context-Aware AI Support Chat")
    st.markdown(
        """
        Chat with **GraphSupport AI**, an intelligent support agent grounded in
        persistent Neo4j graph memory, prior troubleshooting attempts, and authorized tools.
        """
    )

    service = _get_service(settings)
    if not service:
        st.warning(
            "⚠️ **Neo4j is not connected.** "
            "Graph memory and chat persistence require an active database connection."
        )
        return

    # 1. Fetch available customers
    try:
        customers = service.list_customers(limit=50)
    except Exception as err:
        st.error(f"❌ Failed to load customers from Neo4j: {err}")
        return

    if not customers:
        st.info("ℹ️ No registered customers found. Please register a customer in Phase 3 Workbench.")
        return

    # Customer and Session Selector
    top_col1, top_col2 = st.columns([2, 1])
    with top_col1:
        cust_map = {f"{c.name} ({c.email}) [{c.id}]": c for c in customers}
        selected_cust_label = st.selectbox(
            "Select Customer Persona (Identity Boundary)*",
            options=list(cust_map.keys()),
            key="chat_customer_select",
        )
        selected_customer = cust_map[selected_cust_label]

    # Check LLM Configuration State
    with top_col2:
        is_configured = settings.is_llm_configured
        if is_configured:
            st.success(
                f"🟢 **Live LLM Active**\n\n"
                f"Provider: `{settings.llm_provider}`\n\nModel: `{settings.llm_model}`"
            )
            use_mock = False
        else:
            st.warning("⚠️ **LLM Not Configured**\n\n`LLM_API_KEY` missing in `.env`")
            use_mock = st.checkbox(
                "Enable Demo Test Provider",
                value=False,
                help=(
                    "Allows testing agent orchestration, memory, and persistence "
                    "using a local mock provider."
                ),
            )

    # 2. Manage Active Conversation Session
    conv_key = f"active_conv_{selected_customer.id}"
    active_conv_id = st.session_state.get(conv_key)

    # Allow creating new conversation session
    ctrl_col1, ctrl_col2 = st.columns([3, 1])
    with ctrl_col2:
        if st.button("➕ Start New Conversation", use_container_width=True):
            try:
                new_conv = service.start_conversation(
                    customer_id=selected_customer.id,
                    channel="ai_chat",
                )
                st.session_state[conv_key] = new_conv.id
                active_conv_id = new_conv.id
                st.rerun()
            except Exception as err:
                st.error(f"Failed to create conversation: {err}")

    # Fetch recent conversations for this customer
    customer_convs = service.list_customer_conversations(selected_customer.id, limit=10)
    if not active_conv_id:
        if customer_convs:
            active_conv_id = customer_convs[0].id
            st.session_state[conv_key] = active_conv_id
        else:
            try:
                new_conv = service.start_conversation(
                    customer_id=selected_customer.id,
                    channel="ai_chat",
                )
                active_conv_id = new_conv.id
                st.session_state[conv_key] = active_conv_id
            except Exception as err:
                st.error(f"Error starting initial conversation: {err}")
                return

    with ctrl_col1:
        if customer_convs:
            c_options = {f"Session {c.id[:16]}... ({c.status})": c.id for c in customer_convs}
            # Find index
            cur_ids = list(c_options.values())
            cur_idx = cur_ids.index(active_conv_id) if active_conv_id in cur_ids else 0
            sel_conv_label = st.selectbox(
                "Active Conversation Session",
                options=list(c_options.keys()),
                index=cur_idx,
            )
            active_conv_id = c_options[sel_conv_label]
            st.session_state[conv_key] = active_conv_id

    # 3. Display Persistent Conversation History
    messages = service.get_conversation_messages(active_conv_id)
    chat_container = st.container()

    with chat_container:
        if not messages:
            st.info(
                f"💬 Started a new support session with **{selected_customer.name}**. "
                "Type a message below to begin troubleshooting."
            )
        else:
            for msg in messages:
                if msg.sender_type == "customer":
                    with st.chat_message("user"):
                        st.markdown(
                            f"**{selected_customer.name}** ({msg.timestamp.strftime('%H:%M:%S')})"
                        )
                        st.markdown(msg.content)
                else:
                    with st.chat_message("assistant"):
                        st.markdown(f"**GraphSupport AI** ({msg.timestamp.strftime('%H:%M:%S')})")
                        st.markdown(msg.content)

    # 4. Chat Input Box
    user_input = st.chat_input(
        f"Message GraphSupport AI as {selected_customer.name}...",
        key="chat_input_text",
    )

    if user_input:
        if not is_configured and not use_mock:
            st.error(
                "🛑 **Live LLM is not configured.** "
                "To send messages to an AI model, set `LLM_API_KEY` in `.env` "
                "or check 'Enable Demo Test Provider' above to test the orchestrator offline."
            )
            return

        # Initialize appropriate provider
        if use_mock:
            provider = MockLLMProvider()
            st.info("ℹ️ Note: Processing request using local Test Provider simulation.")
        else:
            try:
                provider = get_llm_provider(settings)
            except LLMConfigurationError as err:
                st.error(f"Configuration Error: {err}")
                return

        # Execute Agent turn
        agent = SupportAgent(
            support_service=service,
            llm_provider=provider,
            max_tool_iterations=4,
        )

        with st.spinner("GraphSupport AI is retrieving graph memory and reasoning..."):
            try:
                response = agent.handle_message(
                    customer_id=selected_customer.id,
                    message=user_input,
                    conversation_id=active_conv_id,
                )
                if response.tool_executions:
                    for t_exec in response.tool_executions:
                        status_str = "✅ SUCCESS" if t_exec.success else "❌ FAILED"
                        st.toast(f"Tool `{t_exec.tool_name}`: {status_str}")
                st.rerun()
            except LLMAuthenticationError as err:
                st.error(f"🛑 Provider Authentication Error: {err}")
            except LLMRateLimitError as err:
                st.warning(f"⏳ Rate Limit Exceeded: {err}")
            except LLMTimeoutError as err:
                st.warning(f"⌛ Provider Request Timed Out: {err}")
            except AuthorizationError as err:
                st.error(f"🛑 Security Boundary Violation: {err}")
            except ValidationError as err:
                st.warning(f"⚠️ Input Validation: {err}")
            except GraphSupportError as err:
                st.error(f"❌ Application Error: {err}")
            except Exception as err:
                logger.exception("Unexpected error in chat UI: %s", err)
                st.error(f"❌ Unexpected Error: {err}")
