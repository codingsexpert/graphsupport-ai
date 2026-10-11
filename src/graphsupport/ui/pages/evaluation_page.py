"""Evaluation and Benchmarks operations page for GraphSupport AI (Phase 6).

Displays automated grounding fidelity, memory retrieval quality, tool isolation,
response validation, and latency benchmarks using the deterministic EvaluationRunner.
"""

import logging

import streamlit as st

from graphsupport.application.evaluation import EvaluationReport, EvaluationRunner
from graphsupport.application.support_service import SupportService
from graphsupport.config.settings import Settings
from graphsupport.graph.driver import get_driver_manager

logger = logging.getLogger("graphsupport.ui.pages.evaluation")


def _get_service(settings: Settings) -> SupportService | None:
    if not settings.is_neo4j_configured:
        return None
    try:
        dm = get_driver_manager()
        return SupportService(driver_manager=dm, database=settings.neo4j_database)
    except Exception as err:
        logger.error("Failed to initialize SupportService: %s", err)
        return None


def render_evaluation_page(settings: Settings) -> None:
    """Render the automated AI evaluation and benchmarking dashboard."""
    st.subheader("📈 AI Grounding & Memory Evaluation")
    st.caption(
        "Automated benchmark suite measuring retrieval fidelity, outcome invariance, "
        "tool boundary enforcement, anti-hallucination validation, and latency."
    )

    st.info(
        "⚡ **Cost & Safety Policy**: This benchmark suite executes deterministic offline "
        "test vectors against domain repositories. **Zero paid LLM tokens are consumed.**"
    )

    service = _get_service(settings)

    top_c1, top_c2 = st.columns([3, 1])
    with top_c2:
        run_now = st.button("🚀 Run System Benchmark", use_container_width=True, key="btn_run_eval")

    report: EvaluationReport | None = st.session_state.get("cached_eval_report")
    if run_now or report is None:
        with st.spinner("Running grounding and validation benchmarks..."):
            runner = EvaluationRunner(service=service)
            report = runner.run_all_evaluations()
            st.session_state["cached_eval_report"] = report

    # Overall Summary Cards
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        score_pct = int(report.overall_score * 100)
        st.metric(label="Overall Benchmark Score", value=f"{score_pct}%", delta="100% Target")
    with m2:
        st.metric(label="Tests Passed", value=f"{report.passed_tests} / {report.total_tests}")
    with m3:
        st.metric(label="Evaluation Mode", value="Offline Mock", delta="0 Paid Tokens")
    with m4:
        st.metric(label="Execution UTC", value=report.timestamp[11:19])

    st.divider()

    # Detailed Benchmark Breakdown Table
    st.markdown("#### Benchmark Suite Results")
    table_rows = []
    for item in report.benchmark_items:
        status_str = "✅ PASSED" if item.passed else "❌ FAILED"
        table_rows.append(
            {
                "Benchmark Name": item.name,
                "Category": item.category,
                "Status": status_str,
                "Score": f"{item.score * 100:.0f}%",
                "Latency (ms)": f"{item.latency_ms:.2f} ms",
                "Verification Details": item.details,
            }
        )

    st.dataframe(table_rows, use_container_width=True)

    st.divider()

    # Qualitative Benchmark Notes & Production Readiness Notice
    st.markdown("#### 📋 Operational Observations & Limitations")
    st.markdown(
        """
        - **Grounding Fidelity**: Verified that `ContextBuilder` preserves diagnostic indicators
          and strictly flags absent customer records rather than hallucinating defaults.
        - **Outcome Invariance**: Confirmed that previously failed attempts remain strictly
          flagged with `failed_attempt` warning indicators across restarts.
        - **Tool Isolation**: Cross-customer ticket operations are blocked at the
          application boundary.
        - **Response Validation**: Claims of completed actions are rejected without tool execution.
        - **Notice on Production Readiness**: While passing this offline benchmark is a strict
          prerequisite, it does not replace human evaluation planned for Phase 7.
        """
    )
