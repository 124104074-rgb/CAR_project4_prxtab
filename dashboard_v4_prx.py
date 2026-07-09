"""
dashboard_v4_prx.py

Modular Streamlit dashboard for real-time cerebral autoregulation and CPPopt monitoring.

This version keeps the core real-time processing in this file for safety, while
moving easier-to-edit parts into separate modules:
- config.py              -> settings, colors, speed/window options
- stream_control.py      -> dataset/speed/sheet control sidebar
- patient_info.py        -> patient display from patient_registry.csv
- live_data_reader.py    -> live_data.csv reading and timestamp parsing
- ui/theme.py            -> CSS and font sizes
- ui/cards.py            -> metric cards and badges
- ui/plots.py            -> Plotly graph helpers
- prx_history.py         -> PRx history/tag/duration logic
"""

from datetime import timedelta
import time

import numpy as np
import pandas as pd
import streamlit as st

from analysis_1 import (
    PRX_WINDOW_SAMPLES,
    REAL_SAMPLE_INTERVAL,
    calculate_cpp,
    calculate_mean_cpp,
    calculate_cppopt,
    calculate_prx,
    check_gap,
)

from config import (
    BAD_COLOR,
    CPP_COLOR,
    CPPOPT_COLOR,
    DASHBOARD_REFRESH_SEC,
    DATA_FILE,
    DIFF_COLOR,
    GOOD_COLOR,
    ICP_COLOR,
    MAP_COLOR,
    MAX_CPP_GRAPH_POINTS,
    MAX_CPPOPT_GRAPH_POINTS,
    MAX_PRX_GRAPH_POINTS,
    NEUTRAL_COLOR,
    PRX_AUTOREGULATION_THRESHOLD,
    PRX_COLOR,
    PRX_UPDATE_INTERVAL_SEC,
    TIME_COLOR,
    WINDOW_OPTIONS,
)

from live_data_reader import get_new_rows, parse_timestamp, read_live_csv
from stream_control import render_streaming_controls
from ui.cards import (
    format_live_value,
    is_nan_value,
    render_autoregulation_badge,
    render_metric_card,
    render_patient_box,
    render_side_value,
    trend_arrow,
)
from ui.plots import make_plot_dataframe, render_line_chart
from ui.theme import load_css

from prx_history import (
    add_prx_record,
    add_tag,
    filter_history_from_tag,
    get_current_continuous_state,
    get_status_segments,
    get_tag_by_option,
    get_tag_options,
    history_to_dataframe,
    segments_to_dataframe,
    summarize_autoregulation_duration,
    tags_to_dataframe,
)


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(page_title="CPPopt Monitor", layout="wide")
load_css()


# =========================================================
# SESSION STATE DEFAULTS
# =========================================================

STATE_DEFAULTS = {
    "last_processed_row": 0,
    "map_history": [],
    "icp_history": [],
    "cpp_history": [],
    "prx_history": [],
    "mean_cpp_history": [],
    "prx_history_records": [],
    "prx_tags": [],
    "cpp_plot_time": [],
    "cpp_plot_values": [],
    "prx_plot_time": [],
    "prx_plot_values": [],
    "cppopt_plot_time": [],
    "cppopt_plot_values": [],
    "previous_timestamp": None,
    "last_prx_calculation_time": None,
    "latest_map": np.nan,
    "latest_icp": np.nan,
    "latest_cpp": np.nan,
    "latest_prx": np.nan,
    "latest_cppopt": np.nan,
    "latest_cppopt_minus_cpp": np.nan,
    "previous_map": np.nan,
    "previous_icp": np.nan,
    "previous_cpp": np.nan,
    "previous_prx": np.nan,
    "previous_cppopt": np.nan,
    "previous_cppopt_minus_cpp": np.nan,
    "latest_prx_status": "Waiting for 60 continuous samples",
    "latest_cppopt_status": "Waiting for valid PRx values",
    "last_valid_cppopt": np.nan,
    "last_valid_cppopt_time": None,
    "latest_autoregulation_status": "Not available",
    "latest_gap_message": "",
    "latest_monitor_timestamp": None,
}


def initialize_state() -> None:
    """Initialize all required Streamlit session-state variables."""
    for key, value in STATE_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value.copy() if isinstance(value, list) else value


def reset_realtime_state() -> None:
    """Reset dashboard histories after dataset/sheet restart."""
    for key, value in STATE_DEFAULTS.items():
        st.session_state[key] = value.copy() if isinstance(value, list) else value


# =========================================================
# REAL-TIME PROCESSING HELPERS
# =========================================================


def trim_history() -> None:
    """Keep graph history sizes limited for stable performance."""
    if len(st.session_state.cpp_plot_time) > MAX_CPP_GRAPH_POINTS:
        st.session_state.cpp_plot_time = st.session_state.cpp_plot_time[-MAX_CPP_GRAPH_POINTS:]
        st.session_state.cpp_plot_values = st.session_state.cpp_plot_values[-MAX_CPP_GRAPH_POINTS:]

    if len(st.session_state.prx_plot_time) > MAX_PRX_GRAPH_POINTS:
        st.session_state.prx_plot_time = st.session_state.prx_plot_time[-MAX_PRX_GRAPH_POINTS:]
        st.session_state.prx_plot_values = st.session_state.prx_plot_values[-MAX_PRX_GRAPH_POINTS:]

    if len(st.session_state.cppopt_plot_time) > MAX_CPPOPT_GRAPH_POINTS:
        st.session_state.cppopt_plot_time = st.session_state.cppopt_plot_time[-MAX_CPPOPT_GRAPH_POINTS:]
        st.session_state.cppopt_plot_values = st.session_state.cppopt_plot_values[-MAX_CPPOPT_GRAPH_POINTS:]


def insert_cpp_nan_gap_points(previous_timestamp, current_timestamp) -> None:
    """Insert CPP NaN points for every missing expected monitor sample."""
    missing_timestamp = previous_timestamp + timedelta(seconds=REAL_SAMPLE_INTERVAL)

    while missing_timestamp < current_timestamp:
        st.session_state.cpp_plot_time.append(missing_timestamp)
        st.session_state.cpp_plot_values.append(np.nan)
        missing_timestamp += timedelta(seconds=REAL_SAMPLE_INTERVAL)


def insert_prx_cppopt_nan_gap_points(previous_timestamp, current_timestamp) -> None:
    """Insert PRx and CPPopt NaN points during a detected timestamp gap."""
    missing_timestamp = previous_timestamp + timedelta(seconds=PRX_UPDATE_INTERVAL_SEC)

    while missing_timestamp < current_timestamp:
        st.session_state.prx_plot_time.append(missing_timestamp)
        st.session_state.prx_plot_values.append(np.nan)
        st.session_state.cppopt_plot_time.append(missing_timestamp)
        st.session_state.cppopt_plot_values.append(np.nan)
        missing_timestamp += timedelta(seconds=PRX_UPDATE_INTERVAL_SEC)


def reset_continuous_windows_after_gap() -> None:
    """Reset only rolling clinical windows after a data gap or missing sample."""
    st.session_state.map_history.clear()
    st.session_state.icp_history.clear()
    st.session_state.cpp_history.clear()
    st.session_state.last_prx_calculation_time = None

    st.session_state.latest_map = np.nan
    st.session_state.latest_icp = np.nan
    st.session_state.latest_cpp = np.nan
    st.session_state.latest_prx = np.nan
    st.session_state.latest_cppopt = np.nan
    st.session_state.latest_cppopt_minus_cpp = np.nan

    st.session_state.latest_prx_status = "Waiting for 60 continuous samples after data gap"
    st.session_state.latest_cppopt_status = "Waiting for valid PRx history after data gap"
    st.session_state.latest_autoregulation_status = "Not available"


def update_cppopt_minus_cpp() -> None:
    """Update CPPopt minus current CPP and preserve previous value for trend arrow."""
    st.session_state.previous_cppopt_minus_cpp = st.session_state.latest_cppopt_minus_cpp

    if is_nan_value(st.session_state.latest_cppopt) or is_nan_value(st.session_state.latest_cpp):
        st.session_state.latest_cppopt_minus_cpp = np.nan
    else:
        st.session_state.latest_cppopt_minus_cpp = (
            st.session_state.latest_cppopt - st.session_state.latest_cpp
        )


def process_live_csv() -> None:
    """Read newly appended live_data.csv rows and update dashboard state."""
    try:
        df = read_live_csv(DATA_FILE)

        if st.session_state.last_processed_row > len(df):
            reset_realtime_state()

        new_rows = get_new_rows(df, st.session_state.last_processed_row)

        for _, row in new_rows.iterrows():
            current_timestamp = parse_timestamp(row)
            st.session_state.latest_monitor_timestamp = current_timestamp

            gap_found, gap_sec = check_gap(st.session_state.previous_timestamp, current_timestamp)

            if gap_found:
                insert_cpp_nan_gap_points(st.session_state.previous_timestamp, current_timestamp)
                insert_prx_cppopt_nan_gap_points(st.session_state.previous_timestamp, current_timestamp)
                reset_continuous_windows_after_gap()
                st.session_state.latest_gap_message = (
                    f"Data gap detected: {gap_sec:.0f} seconds from "
                    f"{st.session_state.previous_timestamp.strftime('%H:%M:%S')} to "
                    f"{current_timestamp.strftime('%H:%M:%S')}."
                )
            else:
                st.session_state.latest_gap_message = ""

            map_value = pd.to_numeric(row["mean1"], errors="coerce")
            icp_value = pd.to_numeric(row["mean2"], errors="coerce")

            if np.isnan(map_value) or np.isnan(icp_value):
                st.session_state.previous_map = st.session_state.latest_map
                st.session_state.previous_icp = st.session_state.latest_icp
                st.session_state.previous_cpp = st.session_state.latest_cpp

                st.session_state.latest_map = np.nan
                st.session_state.latest_icp = np.nan
                st.session_state.latest_cpp = np.nan
                st.session_state.latest_prx = np.nan
                st.session_state.latest_prx_status = "MAP or ICP sample is missing"
                st.session_state.latest_autoregulation_status = "Not available"

                st.session_state.cpp_plot_time.append(current_timestamp)
                st.session_state.cpp_plot_values.append(np.nan)
                st.session_state.prx_plot_time.append(current_timestamp)
                st.session_state.prx_plot_values.append(np.nan)
                st.session_state.cppopt_plot_time.append(current_timestamp)
                st.session_state.cppopt_plot_values.append(np.nan)

                reset_continuous_windows_after_gap()
                st.session_state.previous_timestamp = current_timestamp
                update_cppopt_minus_cpp()
                continue

            cpp_value = calculate_cpp(map_value, icp_value)

            st.session_state.previous_map = st.session_state.latest_map
            st.session_state.previous_icp = st.session_state.latest_icp
            st.session_state.previous_cpp = st.session_state.latest_cpp

            st.session_state.latest_map = map_value
            st.session_state.latest_icp = icp_value
            st.session_state.latest_cpp = cpp_value

            st.session_state.map_history.append(map_value)
            st.session_state.icp_history.append(icp_value)
            st.session_state.cpp_history.append(cpp_value)

            st.session_state.cpp_plot_time.append(current_timestamp)
            st.session_state.cpp_plot_values.append(cpp_value)
            st.session_state.previous_timestamp = current_timestamp

            enough_prx_samples = len(st.session_state.map_history) >= PRX_WINDOW_SAMPLES
            first_prx = st.session_state.last_prx_calculation_time is None

            if first_prx:
                prx_due = enough_prx_samples
            else:
                elapsed_seconds = (
                    current_timestamp - st.session_state.last_prx_calculation_time
                ).total_seconds()
                prx_due = enough_prx_samples and elapsed_seconds >= PRX_UPDATE_INTERVAL_SEC

            if prx_due:
                map_window = st.session_state.map_history[-PRX_WINDOW_SAMPLES:]
                icp_window = st.session_state.icp_history[-PRX_WINDOW_SAMPLES:]
                cpp_window = st.session_state.cpp_history[-PRX_WINDOW_SAMPLES:]

                prx_value, prx_status = calculate_prx(map_window, icp_window)
                mean_cpp_value = calculate_mean_cpp(cpp_window)

                st.session_state.previous_prx = st.session_state.latest_prx
                st.session_state.latest_prx = prx_value
                st.session_state.latest_prx_status = (
                    prx_status
                    if not np.isnan(prx_value)
                    else (prx_status if prx_status != "Valid" else "PRx value is unavailable")
                )
                st.session_state.prx_plot_time.append(current_timestamp)
                st.session_state.prx_plot_values.append(prx_value)
                st.session_state.last_prx_calculation_time = current_timestamp

                if np.isnan(prx_value):
                    st.session_state.latest_autoregulation_status = "Not available"
                    st.session_state.latest_cppopt = np.nan
                    st.session_state.latest_cppopt_status = (
                        f"PRx unavailable: {st.session_state.latest_prx_status}"
                    )
                    st.session_state.cppopt_plot_time.append(current_timestamp)
                    st.session_state.cppopt_plot_values.append(np.nan)
                else:
                    add_prx_record(
                        st.session_state.prx_history_records,
                        current_timestamp,
                        prx_value,
                        PRX_AUTOREGULATION_THRESHOLD,
                    )

                    st.session_state.prx_history.append(prx_value)
                    st.session_state.mean_cpp_history.append(mean_cpp_value)

                    if prx_value < PRX_AUTOREGULATION_THRESHOLD:
                        st.session_state.latest_autoregulation_status = "Preserved autoregulation"
                    else:
                        st.session_state.latest_autoregulation_status = "Impaired autoregulation"

                    cppopt_value, cppopt_status = calculate_cppopt(
                        np.asarray(st.session_state.prx_history, dtype=float),
                        np.asarray(st.session_state.mean_cpp_history, dtype=float),
                    )

                    st.session_state.previous_cppopt = st.session_state.latest_cppopt
                    st.session_state.latest_cppopt = cppopt_value
                    st.session_state.latest_cppopt_status = cppopt_status
                    st.session_state.cppopt_plot_time.append(current_timestamp)
                    st.session_state.cppopt_plot_values.append(cppopt_value)

                    if not np.isnan(cppopt_value):
                        st.session_state.last_valid_cppopt = cppopt_value
                        st.session_state.last_valid_cppopt_time = current_timestamp

            update_cppopt_minus_cpp()

        st.session_state.last_processed_row = len(df)
        trim_history()

    except FileNotFoundError:
        st.error("live_data.csv was not found in the same folder as dashboard_v4_prx.py")
    except Exception as error:
        st.error(f"Dashboard error: {error}")


# =========================================================
# RENDERING FUNCTIONS
# =========================================================


def render_header(selected_patient_display: str, selected_dataset_file: str) -> None:
    """Render dashboard title and patient box."""
    header_left, header_right = st.columns([4, 1.2])

    with header_left:
        st.markdown(
            '<div class="main-title">Real-Time Cerebral Monitoring Dashboard</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="subtitle">CPP, PRx and CPPopt monitoring using live CSV data</div>',
            unsafe_allow_html=True,
        )

    with header_right:
        render_patient_box(selected_patient_display, selected_dataset_file)


def render_live_monitoring_tab(cpp_window_label, prx_window_label, cppopt_window_label) -> None:
    """Render the live monitoring tab."""
    cpp_window_minutes = WINDOW_OPTIONS[cpp_window_label]
    prx_window_minutes = WINDOW_OPTIONS[prx_window_label]
    cppopt_window_minutes = WINDOW_OPTIONS[cppopt_window_label]

    st.divider()

    map_col, icp_col, last_cppopt_col, time_col = st.columns([1, 1, 1, 2])

    with map_col:
        render_metric_card(
            "MAP (mmHg)",
            format_live_value(st.session_state.latest_map, 2),
            MAP_COLOR,
            trend_arrow(st.session_state.latest_map, st.session_state.previous_map),
            "Mean arterial pressure",
        )

    with icp_col:
        render_metric_card(
            "ICP (mmHg)",
            format_live_value(st.session_state.latest_icp, 2),
            ICP_COLOR,
            trend_arrow(st.session_state.latest_icp, st.session_state.previous_icp),
            "Intracranial pressure",
        )

    with last_cppopt_col:
        if np.isnan(st.session_state.last_valid_cppopt):
            last_cppopt_value_text = "Not available"
            last_cppopt_subtext = "Last valid CPPopt"
        else:
            last_cppopt_value_text = format_live_value(st.session_state.last_valid_cppopt, 2)
            if st.session_state.last_valid_cppopt_time is None:
                last_cppopt_subtext = "Last valid CPPopt"
            else:
                last_cppopt_subtext = st.session_state.last_valid_cppopt_time.strftime("%H:%M:%S")
        render_metric_card("Last CPPopt", last_cppopt_value_text, CPPOPT_COLOR, "", last_cppopt_subtext)

    with time_col:
        if st.session_state.latest_monitor_timestamp is None:
            monitor_time_text = "Waiting"
            monitor_subtext = "No monitor timestamp received"
        else:
            monitor_time_text = st.session_state.latest_monitor_timestamp.strftime("%H:%M:%S")
            monitor_subtext = st.session_state.latest_monitor_timestamp.strftime("%d-%m-%Y")
        render_metric_card("Current Time", monitor_time_text, TIME_COLOR, "", monitor_subtext)

    if st.session_state.latest_gap_message:
        st.warning(st.session_state.latest_gap_message)

    if np.isnan(st.session_state.latest_prx):
        st.info(f"PRx unavailable: {st.session_state.latest_prx_status}")

    if np.isnan(st.session_state.latest_cppopt):
        st.info(f"CPPopt unavailable: {st.session_state.latest_cppopt_status}")

    st.subheader("CPP vs Time")
    cpp_graph_col, cpp_value_col = st.columns([4, 1])
    with cpp_graph_col:
        cpp_plot = make_plot_dataframe(
            st.session_state.cpp_plot_time,
            st.session_state.cpp_plot_values,
            "CPP",
            cpp_window_minutes,
        )
        render_line_chart(cpp_plot, "CPP", CPP_COLOR, "CPP", chart_key="live_cpp_chart")
    with cpp_value_col:
        render_side_value(
            "CPP",
            format_live_value(st.session_state.latest_cpp, 2),
            CPP_COLOR,
            trend_arrow(st.session_state.latest_cpp, st.session_state.previous_cpp),
            f"Window: {cpp_window_label}",
        )

    st.subheader("PRx vs Time")
    prx_graph_col, prx_value_col = st.columns([4, 1])
    with prx_graph_col:
        prx_plot = make_plot_dataframe(
            st.session_state.prx_plot_time,
            st.session_state.prx_plot_values,
            "PRx",
            prx_window_minutes,
        )
        render_line_chart(prx_plot, "PRx", PRX_COLOR, "PRx", chart_key="live_prx_chart")
    with prx_value_col:
        render_side_value(
            "PRx",
            format_live_value(st.session_state.latest_prx, 3),
            PRX_COLOR,
            trend_arrow(st.session_state.latest_prx, st.session_state.previous_prx),
            f"Window: {prx_window_label}",
        )
        render_autoregulation_badge(st.session_state.latest_autoregulation_status)

    st.subheader("CPPopt vs Time")
    cppopt_graph_col, cppopt_value_col = st.columns([4, 1])
    with cppopt_graph_col:
        cppopt_plot = make_plot_dataframe(
            st.session_state.cppopt_plot_time,
            st.session_state.cppopt_plot_values,
            "CPPopt",
            cppopt_window_minutes,
        )
        render_line_chart(cppopt_plot, "CPPopt", CPPOPT_COLOR, "CPPopt", chart_key="live_cppopt_chart")
    with cppopt_value_col:
        render_side_value(
            "CPPopt",
            format_live_value(st.session_state.latest_cppopt, 2),
            CPPOPT_COLOR,
            trend_arrow(st.session_state.latest_cppopt, st.session_state.previous_cppopt),
            f"Window: {cppopt_window_label}",
        )
        st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
        render_side_value(
            "CPPopt − CPP",
            format_live_value(st.session_state.latest_cppopt_minus_cpp, 2),
            DIFF_COLOR,
            trend_arrow(
                st.session_state.latest_cppopt_minus_cpp,
                st.session_state.previous_cppopt_minus_cpp,
            ),
            "Target difference",
        )


def render_prx_history_tab() -> None:
    """Render the PRx/autoregulation history tab."""
    st.divider()
    st.subheader("PRx / Autoregulation History")

    if st.session_state.latest_monitor_timestamp is None:
        st.info("Waiting for monitor timestamp before tags can be added.")
    else:
        tag_col, tag_info_col = st.columns([1, 3])
        with tag_col:
            if st.button("Add Tag", key="add_prx_history_tag"):
                add_tag(st.session_state.prx_tags, st.session_state.latest_monitor_timestamp)
                st.success("Tag added")
        with tag_info_col:
            st.write(
                f"Current monitor time: "
                f"{st.session_state.latest_monitor_timestamp.strftime('%d-%m-%Y %H:%M:%S')}"
            )

    tag_options = get_tag_options(st.session_state.prx_tags)
    selected_tag_option = st.selectbox(
        "Show PRx history from",
        tag_options,
        index=0,
        key="prx_history_tag_selector",
    )
    selected_tag = get_tag_by_option(st.session_state.prx_tags, selected_tag_option)
    filtered_prx_history = filter_history_from_tag(
        st.session_state.prx_history_records,
        selected_tag,
    )

    summary = summarize_autoregulation_duration(filtered_prx_history, PRX_UPDATE_INTERVAL_SEC)
    continuous_state = get_current_continuous_state(
        st.session_state.prx_history_records,
        PRX_UPDATE_INTERVAL_SEC,
    )

    good_col, bad_col, good_pct_col, bad_pct_col = st.columns(4)
    with good_col:
        render_metric_card("Good Time", summary["good_duration_text"], GOOD_COLOR, "", "PRx < 0.25")
    with bad_col:
        render_metric_card("Bad Time", summary["bad_duration_text"], BAD_COLOR, "", "PRx ≥ 0.25")
    with good_pct_col:
        render_metric_card("Good %", f"{summary['good_percent']:.1f}%", GOOD_COLOR, "", "Selected history")
    with bad_pct_col:
        render_metric_card("Bad %", f"{summary['bad_percent']:.1f}%", BAD_COLOR, "", "Selected history")

    st.markdown("### Current Continuous Autoregulation")
    if continuous_state["status"] == "Good":
        continuous_color = GOOD_COLOR
        continuous_label = "Good / Preserved"
    elif continuous_state["status"] == "Bad":
        continuous_color = BAD_COLOR
        continuous_label = "Bad / Impaired"
    else:
        continuous_color = NEUTRAL_COLOR
        continuous_label = "Not available"

    continuous_col1, continuous_col2 = st.columns(2)
    with continuous_col1:
        since_text = (
            "Not available"
            if continuous_state["since"] is None
            else continuous_state["since"].strftime("%H:%M:%S")
        )
        render_metric_card("Current State", continuous_label, continuous_color, "", f"Since {since_text}")
    with continuous_col2:
        render_metric_card(
            "Continuous Duration",
            continuous_state["duration_text"],
            continuous_color,
            "",
            "Uninterrupted latest state",
        )

    st.subheader("PRx History Graph")
    prx_history_df = history_to_dataframe(filtered_prx_history)
    if prx_history_df.empty:
        st.info("No valid PRx history available yet. PRx History will start after the first valid PRx value.")
    else:
        render_line_chart(prx_history_df, "PRx", PRX_COLOR, "PRx History", chart_key="prx_history_chart")

    st.subheader("Continuous Good/Bad Segments")
    segment_df = segments_to_dataframe(
        get_status_segments(filtered_prx_history, PRX_UPDATE_INTERVAL_SEC)
    )
    if segment_df.empty:
        st.info("No continuous Good/Bad segment available yet.")
    else:
        segment_display_df = segment_df.copy()
        segment_display_df["Start Time"] = pd.to_datetime(segment_display_df["Start Time"]).dt.strftime("%H:%M:%S")
        segment_display_df["End Time"] = pd.to_datetime(segment_display_df["End Time"]).dt.strftime("%H:%M:%S")
        st.dataframe(segment_display_df, use_container_width=True, hide_index=True)

    st.subheader("PRx History Table")
    if prx_history_df.empty:
        st.info("No PRx records to display.")
    else:
        prx_display_df = prx_history_df.copy()
        prx_display_df["Time"] = pd.to_datetime(prx_display_df["Time"]).dt.strftime("%H:%M:%S")
        prx_display_df["PRx"] = prx_display_df["PRx"].map(lambda value: f"{value:.3f}")
        st.dataframe(prx_display_df, use_container_width=True, hide_index=True)

    st.subheader("Tags")
    tag_df = tags_to_dataframe(st.session_state.prx_tags)
    if tag_df.empty:
        st.write("No tags added yet.")
    else:
        tag_display_df = tag_df.copy()
        tag_display_df["Time"] = pd.to_datetime(tag_display_df["Time"]).dt.strftime("%H:%M:%S")
        st.dataframe(tag_display_df, use_container_width=True, hide_index=True)


# =========================================================
# MAIN APP
# =========================================================


def main() -> None:
    initialize_state()

    selected_dataset_file, selected_patient_display, _ = render_streaming_controls(
        on_restart_required=reset_realtime_state
    )

    st.sidebar.markdown("---")
    st.sidebar.header("Graph Window")
    cpp_window_label = st.sidebar.selectbox("CPP graph", list(WINDOW_OPTIONS.keys()), index=0)
    prx_window_label = st.sidebar.selectbox("PRx graph", list(WINDOW_OPTIONS.keys()), index=0)
    cppopt_window_label = st.sidebar.selectbox("CPPopt graph", list(WINDOW_OPTIONS.keys()), index=0)

    process_live_csv()

    render_header(selected_patient_display, selected_dataset_file)

    live_tab, prx_history_tab = st.tabs(["Live Monitoring", "PRx History"])

    with live_tab:
        render_live_monitoring_tab(cpp_window_label, prx_window_label, cppopt_window_label)

    with prx_history_tab:
        render_prx_history_tab()

    time.sleep(DASHBOARD_REFRESH_SEC)
    st.rerun()


if __name__ == "__main__":
    main()
