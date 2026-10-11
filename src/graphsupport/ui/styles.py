"""CSS styles and visual design tokens for the GraphSupport AI Streamlit UI.

Provides clean, enterprise-grade styling, minimal typography, refined status pills,
and uncluttered dashboard containers.
"""

import streamlit as st


def apply_custom_styles() -> None:
    """Inject custom modern CSS into the Streamlit page."""
    css = """
    <style>
    /* Global Typography & Spacing */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        color: #0f172a;
    }

    code, pre {
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* Main Container Padding */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2.5rem !important;
        max-width: 1200px;
    }

    /* Hero Header */
    .gs-header-wrapper {
        margin-bottom: 1.5rem;
        padding-bottom: 1rem;
        border-bottom: 1px solid #e2e8f0;
    }

    .gs-hero-badge {
        display: inline-flex;
        align-items: center;
        padding: 0.25rem 0.65rem;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        text-transform: uppercase;
        background: #f1f5f9;
        color: #334155;
        border: 1px solid #e2e8f0;
        margin-bottom: 0.5rem;
    }

    .gs-title {
        font-size: 1.75rem;
        font-weight: 700;
        letter-spacing: -0.02em;
        color: #0f172a;
        margin-bottom: 0.25rem;
        line-height: 1.25;
    }

    .gs-subtitle {
        font-size: 0.95rem;
        color: #64748b;
        margin-bottom: 0;
        line-height: 1.4;
    }

    /* Status & Metric Cards */
    .gs-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1rem 1.15rem;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.04);
        margin-bottom: 0.75rem;
    }

    .gs-card:hover {
        border-color: #cbd5e1;
    }

    .gs-card-title {
        font-size: 0.8rem;
        font-weight: 500;
        color: #64748b;
        margin-bottom: 0.35rem;
    }

    .gs-card-value {
        font-size: 1.4rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 0.2rem;
    }

    .gs-card-desc {
        font-size: 0.8rem;
        color: #64748b;
        line-height: 1.35;
    }

    /* Minimal Pill Badges */
    .gs-pill-success {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.15rem 0.5rem;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 500;
        background: #ecfdf5;
        color: #047857;
        border: 1px solid #a7f3d0;
    }

    .gs-pill-warning {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.15rem 0.5rem;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 500;
        background: #fffbeb;
        color: #b45309;
        border: 1px solid #fde68a;
    }

    .gs-pill-neutral {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.15rem 0.5rem;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 500;
        background: #f8fafc;
        color: #475569;
        border: 1px solid #e2e8f0;
    }

    /* Sidebar Status Box */
    .gs-sidebar-status {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 0.65rem 0.75rem;
        margin-top: 0.5rem;
        font-size: 0.8rem;
    }

    .gs-status-item {
        display: flex;
        align-items: center;
        gap: 0.45rem;
        margin-bottom: 0.3rem;
        color: #334155;
        font-weight: 500;
    }

    .gs-status-item:last-child {
        margin-bottom: 0;
    }

    .gs-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
    }

    .gs-dot-green {
        background-color: #10b981;
    }

    .gs-dot-amber {
        background-color: #f59e0b;
    }

    .gs-dot-gray {
        background-color: #94a3b8;
    }

    /* Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 1.5rem;
        border-bottom: 1px solid #e2e8f0;
    }

    .stTabs [data-baseweb="tab"] {
        padding-top: 0.5rem;
        padding-bottom: 0.75rem;
        font-weight: 500;
        font-size: 0.9rem;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
