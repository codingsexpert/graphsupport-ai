"""UI module for GraphSupport AI Streamlit dashboard (Phase 6)."""

from graphsupport.ui.chat import render_phase5_support_chat
from graphsupport.ui.components import (
    render_architecture_overview,
    render_database_control_panel,
    render_header,
    render_phase_roadmap,
    render_safe_config_section,
    render_status_cards,
)
from graphsupport.ui.data_management import render_phase3_data_management
from graphsupport.ui.memory_inspector import render_phase4_memory_inspector
from graphsupport.ui.navigation import NAV_OPTIONS, render_sidebar
from graphsupport.ui.pages import (
    render_chat_page,
    render_conversations_page,
    render_customers_page,
    render_evaluation_page,
    render_graph_explorer_page,
    render_overview_page,
    render_products_page,
    render_system_health_page,
    render_ticket_details_page,
    render_tickets_page,
)
from graphsupport.ui.styles import apply_custom_styles

__all__ = [
    "NAV_OPTIONS",
    "apply_custom_styles",
    "render_architecture_overview",
    "render_chat_page",
    "render_conversations_page",
    "render_customers_page",
    "render_database_control_panel",
    "render_evaluation_page",
    "render_graph_explorer_page",
    "render_header",
    "render_memory_inspector",
    "render_overview_page",
    "render_phase3_data_management",
    "render_phase4_memory_inspector",
    "render_phase5_support_chat",
    "render_phase_roadmap",
    "render_products_page",
    "render_safe_config_section",
    "render_sidebar",
    "render_status_cards",
    "render_system_health_page",
    "render_ticket_details_page",
    "render_tickets_page",
]
