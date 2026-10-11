"""GraphSupport AI - Main Streamlit Application Entrypoint.

Modular dashboard router providing clean navigation across operations pages:
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

from graphsupport.config import get_settings
from graphsupport.core import check_health, configure_logging
from graphsupport.ui import (
    apply_custom_styles,
    render_chat_page,
    render_conversations_page,
    render_customers_page,
    render_evaluation_page,
    render_graph_explorer_page,
    render_header,
    render_overview_page,
    render_products_page,
    render_sidebar,
    render_system_health_page,
    render_ticket_details_page,
    render_tickets_page,
)


def main() -> None:
    """Initialize and route the GraphSupport AI operational dashboard."""
    # 1. Load typed settings & initialize structured logging
    settings = get_settings()
    configure_logging(settings)

    # 2. Configure Streamlit page layout
    st.set_page_config(
        page_title=f"{settings.app_name} - Support Operations",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # 3. Apply custom design system styles
    apply_custom_styles()

    # 4. Perform local non-sensitive health check
    health = check_health(settings, verify_database=False)

    # 5. Render sidebar navigation & get active page
    selected_page = render_sidebar(settings, health)

    # 6. Render main hero header
    render_header(
        title="GraphSupport AI",
        subtitle=(
            "Context-aware customer support engine powered by Neo4j graph intelligence "
            "and AI reasoning."
        ),
        badge="Enterprise Support Intelligence",
    )

    # 7. Route to selected page module
    if selected_page == "Overview":
        render_overview_page(settings)
    elif selected_page == "Support Chat":
        render_chat_page(settings)
    elif selected_page == "Customers":
        render_customers_page(settings)
    elif selected_page == "Products":
        render_products_page(settings)
    elif selected_page == "Tickets":
        render_tickets_page(settings)
    elif selected_page == "Ticket Details":
        render_ticket_details_page(settings)
    elif selected_page == "Conversation History":
        render_conversations_page(settings)
    elif selected_page == "Graph Explorer":
        render_graph_explorer_page(settings)
    elif selected_page == "System Health":
        render_system_health_page(settings)
    elif selected_page == "Evaluation":
        render_evaluation_page(settings)
    else:
        render_overview_page(settings)


if __name__ == "__main__":
    main()
