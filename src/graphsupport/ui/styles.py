"""CSS styles and visual design tokens for the GraphSupport AI Streamlit UI.

Provides polished styling, status badges, metrics cards, and container styling.
"""

import streamlit as st


def apply_custom_styles() -> None:
    """Inject custom modern CSS into the Streamlit page."""
    css = """
    <style>
    /* Global Typography & Spacing */
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    code, pre {
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* Main Container Padding */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 3rem !important;
        max-width: 1100px;
    }

    /* Hero Header */
    .gs-hero-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.35rem 0.85rem;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        background: rgba(56, 189, 248, 0.12);
        color: #0284c7;
        border: 1px solid rgba(56, 189, 248, 0.35);
        margin-bottom: 0.75rem;
    }

    .gs-title {
        font-size: 2.25rem;
        font-weight: 700;
        letter-spacing: -0.03em;
        color: #0f172a;
        margin-bottom: 0.25rem;
    }

    .gs-subtitle {
        font-size: 1.05rem;
        color: #64748b;
        margin-bottom: 1.5rem;
        line-height: 1.5;
    }

    /* Status & Metric Cards */
    .gs-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1.25rem;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
        margin-bottom: 1rem;
    }

    .gs-card:hover {
        border-color: #cbd5e1;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.07);
    }

    .gs-card-title {
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #64748b;
        margin-bottom: 0.5rem;
    }

    .gs-card-value {
        font-size: 1.35rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 0.25rem;
    }

    .gs-card-desc {
        font-size: 0.85rem;
        color: #475569;
        line-height: 1.4;
    }

    /* Pill Badges */
    .gs-pill-success {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
        background: #dcfce7;
        color: #15803d;
        border: 1px solid #bbf7d0;
    }

    .gs-pill-warning {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
        background: #fef3c7;
        color: #b45309;
        border: 1px solid #fde68a;
    }

    .gs-pill-neutral {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
        background: #f1f5f9;
        color: #475569;
        border: 1px solid #e2e8f0;
    }

    /* Phase Timeline Box */
    .gs-phase-item {
        border-left: 3px solid #e2e8f0;
        padding-left: 1rem;
        margin-bottom: 1.25rem;
        position: relative;
    }

    .gs-phase-item.active {
        border-left-color: #0284c7;
    }

    .gs-phase-title {
        font-size: 0.95rem;
        font-weight: 700;
        color: #0f172a;
    }

    .gs-phase-desc {
        font-size: 0.85rem;
        color: #64748b;
        margin-top: 0.2rem;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
