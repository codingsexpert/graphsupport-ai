"""Sidebar and navigation components for GraphSupport AI."""

import streamlit as st

from graphsupport.config.settings import Settings
from graphsupport.core.health import HealthStatus


def render_sidebar(settings: Settings, health: HealthStatus) -> None:
    """Render the application sidebar with metadata and system controls."""
    with st.sidebar:
        st.title(f"{settings.app_name}")
        st.caption(f"v{settings.app_version} • {settings.app_env.value.title()}")

        st.divider()

        st.markdown("### Active Phase")
        st.info("Phase 1: Professional Foundation")

        st.markdown("### Subsystem Readiness")
        st.markdown(f"- **Core Runtime**: `{health.status.upper()}`")
        neo4j_txt = "Configured" if health.neo4j.configured else "Deferred (Phase 2)"
        st.markdown(f"- **Neo4j Graph**: `{neo4j_txt}`")
        llm_txt = "Configured" if health.llm.configured else "Deferred (Phase 5)"
        st.markdown(f"- **LLM Reasoning**: `{llm_txt}`")

        st.divider()

        st.markdown("### Development Tools")
        st.markdown(
            """
            - **Linter**: Ruff
            - **Test Suite**: Pytest
            - **Settings**: Pydantic Settings
            - **UI Framework**: Streamlit
            """
        )

        st.caption(f"Last checked: {health.timestamp[:19]} UTC")
