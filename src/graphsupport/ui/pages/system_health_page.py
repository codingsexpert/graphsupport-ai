"""System Health operations page for GraphSupport AI (Phase 6).

Provides deep runtime diagnostics, safe configuration audits, explicit Neo4j connectivity
testing, schema validation, and health verification without leaking credentials.
"""

import logging

import streamlit as st

from graphsupport.config.settings import Settings
from graphsupport.core.health import check_health
from graphsupport.graph.driver import get_driver_manager
from graphsupport.graph.schema import initialize_schema, inspect_schema

logger = logging.getLogger("graphsupport.ui.pages.system_health")


def render_system_health_page(settings: Settings) -> None:
    """Render the System Health diagnostic dashboard."""
    st.subheader("🩺 System Health & Infrastructure Diagnostics")
    st.caption(
        "Audit core application runtime readiness, Neo4j connection pooling, schema constraints, "
        "and AI provider configuration without exposing secrets or credentials."
    )

    # 1. Health Status Overview
    h_col1, h_col2 = st.columns([3, 1])
    with h_col2:
        verify_db_live = st.button("⚡ Test Live Connection", use_container_width=True)

    # Cache health in session state unless explicit test is requested
    if verify_db_live or "cached_health_status" not in st.session_state:
        with st.spinner("Checking subsystem connectivity..."):
            health = check_health(
                settings, verify_database=verify_db_live or settings.is_neo4j_configured
            )
            st.session_state["cached_health_status"] = health
    else:
        health = st.session_state["cached_health_status"]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric(
            label="Core Runtime",
            value=health.status.upper(),
            delta=f"Python {health.python_version}",
        )
    with c2:
        st.metric(label="Environment", value=health.environment.upper(), delta=health.platform_info)
    with c3:
        n_val = (
            "Connected"
            if health.neo4j.reachability == "reachable"
            else "Configured"
            if health.neo4j.configured
            else "Not Set"
        )
        st.metric(label="Neo4j Aura", value=n_val, delta=health.neo4j.reachability)
    with c4:
        llm_val = settings.llm_provider.value.title()
        st.metric(
            label="AI Reasoning",
            value=llm_val,
            delta="Key Set" if settings.is_llm_configured else "Mock Mode",
        )

    st.divider()

    # 2. Neo4j Operations & Schema Inspection
    st.markdown("### 🗄️ Neo4j Database & Schema Operations")
    s_col1, s_col2 = st.columns(2)

    with s_col1:
        with st.container(border=True):
            st.markdown("##### ⚡ Schema Constraints & Indexes")
            st.caption(
                "Apply idempotent uniqueness constraints and index definitions via "
                "`initialize_schema`."
            )
            if st.button(
                "Initialize / Verify Schema", use_container_width=True, key="btn_init_schema"
            ):
                if not settings.is_neo4j_configured:
                    st.error("Neo4j is not configured in `.env`.")
                else:
                    try:
                        dm = get_driver_manager()
                        report = initialize_schema(
                            dm.get_driver(), database=settings.neo4j_database
                        )
                        dur_ms = report.duration_ms
                        st.success(f"Applied {report.succeeded}/{report.total} in {dur_ms:.1f}ms.")
                    except Exception as err:
                        st.error(f"Schema application failed: {err}")

    with s_col2:
        with st.container(border=True):
            st.markdown("##### 🔍 Inspect Existing Graph Schema")
            st.caption("Query current database constraints and index metadata.")
            if st.button(
                "Inspect Active Constraints", use_container_width=True, key="btn_inspect_schema"
            ):
                if not settings.is_neo4j_configured:
                    st.error("Neo4j is not configured.")
                else:
                    try:
                        dm = get_driver_manager()
                        schema_info = inspect_schema(
                            dm.get_driver(), database=settings.neo4j_database
                        )
                        st.markdown(f"- **Active Constraints**: {len(schema_info.constraints)}")
                        for c in schema_info.constraints:
                            st.caption(f"• `{c.get('name')}`: `{c.get('description', '')}`")
                        st.markdown(f"- **Active Indexes**: {len(schema_info.indexes)}")
                    except Exception as err:
                        st.error(f"Inspection failed: {err}")

    st.divider()

    # 3. Safe Configuration Audit
    st.markdown("### 🔒 Safe Configuration Audit")
    safe_summary = settings.safe_summary()
    st.dataframe(
        [{"Parameter": k, "Configured Value": str(v)} for k, v in safe_summary.items()],
        use_container_width=True,
    )
    st.caption(
        "Notice: Sensitive credentials (`neo4j_password`, `llm_api_key`) are masked and isolated."
    )
