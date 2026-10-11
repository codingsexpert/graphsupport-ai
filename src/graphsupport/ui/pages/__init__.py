"""Modular Streamlit dashboard pages for GraphSupport AI (Phase 6)."""

from graphsupport.ui.pages.chat_page import render_chat_page
from graphsupport.ui.pages.conversations_page import render_conversations_page
from graphsupport.ui.pages.customers_page import render_customers_page
from graphsupport.ui.pages.evaluation_page import render_evaluation_page
from graphsupport.ui.pages.graph_explorer_page import render_graph_explorer_page
from graphsupport.ui.pages.overview import render_overview_page
from graphsupport.ui.pages.products_page import render_products_page
from graphsupport.ui.pages.system_health_page import render_system_health_page
from graphsupport.ui.pages.ticket_details_page import render_ticket_details_page
from graphsupport.ui.pages.tickets_page import render_tickets_page

__all__ = [
    "render_chat_page",
    "render_conversations_page",
    "render_customers_page",
    "render_evaluation_page",
    "render_graph_explorer_page",
    "render_overview_page",
    "render_products_page",
    "render_system_health_page",
    "render_ticket_details_page",
    "render_tickets_page",
]
