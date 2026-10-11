"""Graph Explorer operations page for GraphSupport AI (Phase 6).

Provides an interactive, read-only visualization of the connected Neo4j property graph.
Visualizes Customers, Products, Tickets, Issues, Diagnostic Steps, Resolutions, and Conversations
with bounded limits and zero user-provided Cypher execution.
"""

import html
import json
import logging

import streamlit as st
import streamlit.components.v1 as components

from graphsupport.application.support_service import SupportService
from graphsupport.config.settings import Settings
from graphsupport.graph.driver import get_driver_manager

logger = logging.getLogger("graphsupport.ui.pages.graph_explorer")

NODE_COLORS = {
    "Customer": "#3b82f6",  # Blue
    "Product": "#8b5cf6",  # Purple
    "Ticket": "#f59e0b",  # Amber
    "Issue": "#ef4444",  # Red
    "Step": "#06b6d4",  # Cyan
    "Resolution": "#10b981",  # Green
    "Conversation": "#64748b",  # Slate
}


def _get_service(settings: Settings) -> SupportService | None:
    if not settings.is_neo4j_configured:
        return None
    try:
        dm = get_driver_manager()
        return SupportService(driver_manager=dm, database=settings.neo4j_database)
    except Exception as err:
        logger.error("Failed to initialize SupportService: %s", err)
        return None


def _generate_vis_html(nodes: list[dict], edges: list[dict]) -> str:
    """Generate standalone HTML/JS with vis.js network visualization."""
    vis_nodes = []
    for n in nodes:
        ntype = n.get("type", "Node")
        color = NODE_COLORS.get(ntype, "#64748b")
        prop_str = "<br>".join(
            [
                f"<b>{k}</b>: {html.escape(str(v))}"
                for k, v in n.get("properties", {}).items()
                if k != "metadata"
            ]
        )
        vis_nodes.append(
            {
                "id": n["id"],
                "label": n.get("label", n["id"]),
                "title": f"<b>{ntype}</b><br>{prop_str}",
                "color": {
                    "background": color,
                    "border": "#1e293b",
                    "highlight": {"background": "#38bdf8", "border": "#0284c7"},
                },
                "font": {"color": "#0f172a", "face": "Plus Jakarta Sans, sans-serif", "size": 12},
                "shape": "dot",
                "size": 18 if ntype in ("Customer", "Ticket") else 14,
            }
        )

    vis_edges = []
    for e in edges:
        vis_edges.append(
            {
                "from": e["source"],
                "to": e["target"],
                "label": e.get("type", ""),
                "arrows": "to",
                "font": {"size": 9, "align": "middle", "color": "#64748b"},
                "color": {"color": "#cbd5e1", "highlight": "#0284c7"},
                "smooth": {"type": "continuous"},
            }
        )

    nodes_json = json.dumps(vis_nodes)
    edges_json = json.dumps(vis_edges)

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
        <style type="text/css">
            #mynetwork {{
                width: 100%;
                height: 480px;
                border: 1px solid #e2e8f0;
                background-color: #f8fafc;
                border-radius: 8px;
            }}
        </style>
    </head>
    <body>
        <div id="mynetwork"></div>
        <script type="text/javascript">
            var nodes = new vis.DataSet({nodes_json});
            var edges = new vis.DataSet({edges_json});
            var container = document.getElementById('mynetwork');
            var data = {{ nodes: nodes, edges: edges }};
            var options = {{
                physics: {{
                    solver: 'forceAtlas2Based',
                    forceAtlas2Based: {{
                        gravitationalConstant: -35,
                        centralGravity: 0.005,
                        springLength: 80,
                        springConstant: 0.18
                    }},
                    stabilization: {{ iterations: 120 }}
                }},
                interaction: {{
                    hover: true,
                    tooltipDelay: 150,
                    zoomView: true
                }}
            }};
            var network = new vis.Network(container, data, options);
        </script>
    </body>
    </html>
    """


def render_graph_explorer_page(settings: Settings) -> None:
    """Render the Graph Explorer visualization page."""
    st.subheader("Knowledge Graph Explorer")
    st.caption(
        "Interactive topology visualizer traversing real relationships across Customers, Products, "
        "Support Tickets, Troubleshooting Steps, Resolutions, and Conversations."
    )

    service = _get_service(settings)
    if not service:
        st.warning("**Neo4j is not connected.** Graph visualization is unavailable.")
        return

    # Scope Selection Controls
    c_scope1, c_scope2, c_scope3 = st.columns([2, 2, 1])
    with c_scope1:
        focus_mode = st.selectbox(
            "Graph Focus Scope",
            options=[
                "Recent Topology (Overview)",
                "Focus on Specific Customer",
                "Focus on Specific Ticket",
            ],
            key="graph_focus_mode",
        )

    selected_cust_id = None
    selected_tkt_id = None

    with c_scope2:
        if focus_mode == "Focus on Specific Customer":
            custs = service.list_customers(limit=50)
            if custs:
                c_opts = {f"{c.name} ({c.id})": c.id for c in custs}
                sel_label = st.selectbox("Select Customer", options=list(c_opts.keys()))
                selected_cust_id = c_opts[sel_label]
            else:
                st.info("No customers found.")
        elif focus_mode == "Focus on Specific Ticket":
            tkts = service.list_all_tickets(limit=50)
            if tkts:
                t_opts = {f"{t.title} ({t.id})": t.id for t in tkts}
                sel_label = st.selectbox("Select Ticket", options=list(t_opts.keys()))
                selected_tkt_id = t_opts[sel_label]
            else:
                st.info("No tickets found.")

    with c_scope3:
        max_nodes = st.slider("Max Nodes", min_value=10, max_value=60, value=30, step=5)

    # Fetch Subgraph
    try:
        subgraph = service.get_subgraph(
            customer_id=selected_cust_id,
            ticket_id=selected_tkt_id,
            max_nodes=max_nodes,
        )
    except Exception as err:
        st.error(f"Failed to query graph topology: {err}")
        return

    nodes = subgraph.get("nodes", [])
    edges = subgraph.get("edges", [])

    # Legend Row
    st.markdown("##### Entity Legend")
    leg_cols = st.columns(len(NODE_COLORS))
    for col, (etype, color) in zip(leg_cols, NODE_COLORS.items(), strict=False):
        col.markdown(
            f"<span style='color: {color}; font-size: 1.2rem;'>●</span> **{etype}**",
            unsafe_allow_html=True,
        )

    if not nodes:
        st.info("No nodes returned for the selected graph focus.")
        return

    st.markdown(f"**Loaded Subgraph**: {len(nodes)} nodes • {len(edges)} relationships")

    # Render interactive network
    html_content = _generate_vis_html(nodes, edges)
    components.html(html_content, height=500)

    # Structured Table Fallback
    with st.expander("Inspect Raw Subgraph Nodes & Edges"):
        tab_nodes, tab_edges = st.tabs(["Nodes Table", "Edges Table"])
        with tab_nodes:
            n_table = [{"ID": n["id"], "Type": n["type"], "Label": n["label"]} for n in nodes]
            st.dataframe(n_table, use_container_width=True)
        with tab_edges:
            st.dataframe(edges, use_container_width=True)
