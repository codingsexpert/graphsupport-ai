"""GraphSupport AI - Main Streamlit Application Entrypoint.

Provides a clean dashboard presenting system readiness, architectural overview,
safe runtime configuration, and project phase status.
"""

import streamlit as st

from graphsupport.config import get_settings
from graphsupport.core import check_health, configure_logging
from graphsupport.ui import (
    apply_custom_styles,
    render_architecture_overview,
    render_header,
    render_phase_roadmap,
    render_safe_config_section,
    render_sidebar,
    render_status_cards,
)


def main() -> None:
    """Initialize and render the GraphSupport AI Phase 1 landing dashboard."""
    # 1. Load typed settings & initialize structured logging
    settings = get_settings()
    configure_logging(settings)

    # 2. Configure Streamlit page layout
    st.set_page_config(
        page_title=f"{settings.app_name} - Foundation",
        page_icon="🕸️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # 3. Apply custom design system styles
    apply_custom_styles()

    # 4. Perform local non-sensitive health check
    health = check_health(settings)

    # 5. Render sidebar
    render_sidebar(settings, health)

    # 6. Render main content areas
    render_header(
        title="GraphSupport AI",
        subtitle=(
            "Context-aware customer support engine powered by Neo4j graph intelligence "
            "and cross-session memory."
        ),
        phase_name=health.current_phase,
    )

    st.markdown(
        """
        > **Phase 1 Status**: The core architecture, configuration system, structured logging,
        > and test infrastructure are operational. Integration with the Neo4j graph database
        > is scheduled for **Phase 2**, and the LLM reasoning agent is scheduled for **Phase 5**.
        """
    )

    # 7. Render status cards
    render_status_cards(health)

    st.divider()

    # 8. Render architecture details
    render_architecture_overview()

    st.divider()

    # 9. Render safe configuration inspection
    render_safe_config_section(settings)

    st.divider()

    # 10. Render phased roadmap
    render_phase_roadmap()


if __name__ == "__main__":
    main()
