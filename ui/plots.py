"""
ui/plots.py

Reusable plotting helpers for the dashboard.
"""

from datetime import timedelta

import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as go
    HAVE_PLOTLY = True
except Exception:
    HAVE_PLOTLY = False


def crop_to_window(times, values, minutes):
    """Return only graph points inside the selected time window."""
    if len(times) == 0:
        return [], []

    latest_time = max(times)
    start_time = latest_time - timedelta(minutes=minutes)

    filtered_times = []
    filtered_values = []

    for timestamp, value in zip(times, values):
        if timestamp >= start_time:
            filtered_times.append(timestamp)
            filtered_values.append(value)

    return filtered_times, filtered_values


def make_plot_dataframe(times, values, value_name: str, window_minutes: int):
    """Build a DataFrame for plotting a selected time window."""
    filtered_times, filtered_values = crop_to_window(times, values, window_minutes)
    return pd.DataFrame({"Time": filtered_times, value_name: filtered_values})


def render_line_chart(
    plot_df,
    value_column: str,
    color: str,
    title: str,
    height: int = 310,
    chart_key: str | None = None,
) -> None:
    """Render a Plotly line chart with NaN gaps preserved.

    chart_key is important because Streamlit can create duplicate
    element IDs when two Plotly charts have similar structure.
    Every chart in the dashboard should therefore get a unique key.
    """
    if plot_df.empty:
        st.info(f"Waiting for {title} data...")
        return

    if HAVE_PLOTLY:
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=plot_df["Time"],
                y=plot_df[value_column],
                mode="lines",
                line=dict(color=color, width=2.5),
                connectgaps=False,
                name=value_column,
            )
        )
        fig.update_layout(
            height=height,
            margin=dict(l=10, r=10, t=20, b=10),
            xaxis=dict(tickformat="%H:%M:%S", title="TTTime"),
            yaxis=dict(title=value_column),
            showlegend=False,
            template="plotly_white",
        )
        if chart_key is None:
            chart_key = f"plotly_{title}_{value_column}_{height}".replace(" ", "_").lower()

        st.plotly_chart(fig, use_container_width=True, key=chart_key)
        return

    fallback_df = plot_df.copy()
    fallback_df["Time"] = pd.to_datetime(fallback_df["Time"]).dt.strftime("%H:%M:%S")
    st.line_chart(fallback_df.set_index("Time"), use_container_width=True)
