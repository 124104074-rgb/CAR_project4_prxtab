"""
ui/cards.py

Reusable Streamlit/HTML cards for the dashboard.
"""

import numpy as np
import streamlit as st


def is_nan_value(value) -> bool:
    """Return True when value is None, NaN, or not numeric."""
    try:
        return value is None or np.isnan(value)
    except TypeError:
        return True


def format_live_value(value, decimals: int = 2) -> str:
    """Format numeric live values for dashboard display."""
    if is_nan_value(value):
        return "Not available"
    return f"{value:.{decimals}f}"


def trend_arrow(current_value, previous_value) -> str:
    """Return trend arrow comparing current and previous numeric values."""
    if is_nan_value(current_value) or is_nan_value(previous_value):
        return ""
    if current_value > previous_value:
        return "↑"
    if current_value < previous_value:
        return "↓"
    return "→"


def render_metric_card(label: str, value_text: str, color: str, arrow: str = "", subtext: str = "") -> None:
    """Render a large ICU-style top metric card."""
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value" style="color:{color};">{value_text} {arrow}</div>
            <div class="metric-sub">{subtext}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_side_value(title: str, value_text: str, color: str, arrow: str = "", caption: str = "") -> None:
    """Render the value card placed beside a graph."""
    st.markdown(
        f"""
        <div class="side-value-card">
            <div class="side-title" style="color:{color};">{title}</div>
            <div class="side-value" style="color:{color};">{value_text} {arrow}</div>
            <div class="side-caption">{caption}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_autoregulation_badge(status: str) -> None:
    """Render color-coded autoregulation status badge."""
    if status == "Preserved autoregulation":
        st.markdown('<div class="auto-good">🟢 PRESERVED</div>', unsafe_allow_html=True)
    elif status == "Impaired autoregulation":
        st.markdown('<div class="auto-bad">🔴 IMPAIRED</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="auto-na">⚪ NOT AVAILABLE</div>', unsafe_allow_html=True)


def render_patient_box(patient_display: str, source_file: str) -> None:
    """Render patient name/age/gender box in the top-right header."""
    st.markdown(
        f"""
        <div class="patient-box">
            <div class="patient-title">Patient</div>
            <div class="patient-value">{patient_display}</div>
            <div class="patient-file">{source_file}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
