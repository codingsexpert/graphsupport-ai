"""GraphSupport AI - Main Streamlit Application Entrypoint.

Provides a clean dashboard presenting system readiness, architectural overview,
safe runtime configuration, Neo4j connectivity controls, and project phase status.
"""

import streamlit as st

from graphsupport.config import get_settings
from graphsupport.core import check_health, configure_logging
from graphsupport.ui import (
    apply_custom_styles,
    render_architecture_overview,
    render_database_control_panel,
    render_header,
    render_phase3_data_management,
    render_phase4_memory_inspector,
    render_phase_roadmap,
    render_safe_config_section,
    render_sidebar,
    render_status_cards,
)


def main() -> None:
    """Initialize and render the GraphSupport AI dashboard."""
    # 1. Load typed settings & initialize structured logging
    settings = get_settings()
    configure_logging(settings)

    # 2. Configure Streamlit page layout
    st.set_page_config(
        page_title=f"{settings.app_name} - Customer Support Data Layer",
        page_icon="🕸️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # 3. Apply custom design system styles
    apply_custom_styles()

    # 4. Perform local non-sensitive health check (no expensive network query on initial rerun)
    health = check_health(settings, verify_database=False)

    # 5. Render sidebar
    render_sidebar(settings, health)

    # 6. Render main content areas
    render_header(
        title="GraphSupport AI",
        subtitle=(
            "Context-aware customer support engine powered by Neo4j graph intelligence "
            "and cross-session memory."
        ),
        phase_name="Phase 4: Persistent Graph Memory & Retrieval",
    )

    st.markdown(
        """
        > **Phase 4 Status**: Persistent graph memory & context retrieval is active. Customer
        > knowledge subgraphs are deterministically retrieved and ranked with outcome fidelity
        > from Neo4j across sessions.
        """
    )

    # 7. Render status cards
    render_status_cards(health)

    st.divider()

    # 8. Render Phase 4 Graph Memory Inspector
    render_phase4_memory_inspector(settings)

    st.divider()

    # 9. Render Phase 3 Customer Support Workbench
    render_phase3_data_management(settings)

    st.divider()

    # 9. Render interactive Neo4j database controls
    render_database_control_panel(settings)

    st.divider()

    # 9. Render architecture details
    render_architecture_overview()

    st.divider()

    # 10. Render safe configuration inspection
    render_safe_config_section(settings)

    st.divider()

    # 11. Render phased roadmap
    render_phase_roadmap()


if __name__ == "__main__":
    main()
