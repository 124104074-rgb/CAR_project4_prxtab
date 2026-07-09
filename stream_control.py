"""
stream_control.py

Dashboard sidebar controls for dataset selection, Excel sheet selection,
writing speed, run/pause, loop mode, and stream_config.json updates.
"""

import json
import os
import time
from pathlib import Path
from typing import Callable, Dict, Tuple

import pandas as pd
import streamlit as st

from config import (
    CONFIG_FILE,
    DATA_FILE,
    DATASET_FOLDER,
    DEFAULT_STREAM_CONFIG,
    PATIENT_REGISTRY_FILE,
    SPEED_OPTIONS,
    SUPPORTED_DATA_EXTENSIONS,
)
from patient_info import get_patient_display


def write_json_atomic(file_path: str, data: Dict) -> None:
    """Write JSON safely so writer.py never reads a half-written file."""
    temp_file = f"{file_path}.tmp"
    with open(temp_file, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)
    os.replace(temp_file, file_path)


def read_stream_config() -> Dict:
    """Read stream_config.json, creating a default one if missing."""
    if not Path(CONFIG_FILE).exists():
        write_json_atomic(CONFIG_FILE, DEFAULT_STREAM_CONFIG)
        return DEFAULT_STREAM_CONFIG.copy()

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as file:
            config = json.load(file)
        for key, value in DEFAULT_STREAM_CONFIG.items():
            config.setdefault(key, value)
        return config
    except Exception:
        return DEFAULT_STREAM_CONFIG.copy()


def list_dataset_files():
    """Find CSV/XLSX/XLS files available in datasets/ and project root."""
    dataset_files = []
    dataset_path = Path(DATASET_FOLDER)

    if dataset_path.exists():
        for file_path in sorted(dataset_path.iterdir()):
            if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_DATA_EXTENSIONS:
                dataset_files.append(file_path.name)

    for file_path in sorted(Path(".").iterdir()):
        if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_DATA_EXTENSIONS:
            if file_path.name not in {DATA_FILE, PATIENT_REGISTRY_FILE}:
                if file_path.name not in dataset_files:
                    dataset_files.append(file_path.name)

    return dataset_files


def resolve_dataset_for_dashboard(file_name: str) -> Path:
    """Resolve selected dataset filename to an actual file path."""
    direct_path = Path(file_name)
    if direct_path.exists():
        return direct_path

    dataset_path = Path(DATASET_FOLDER) / file_name
    if dataset_path.exists():
        return dataset_path

    return direct_path


def get_excel_sheet_options(file_name: str):
    """Return Excel workbook sheet names for dashboard selector."""
    file_path = resolve_dataset_for_dashboard(file_name)
    try:
        excel_file = pd.ExcelFile(file_path)
        return excel_file.sheet_names
    except Exception:
        return []


def render_streaming_controls(on_restart_required: Callable[[], None] | None = None) -> Tuple[str, str, Dict]:
    """
    Render dashboard sidebar streaming controls.

    Dataset/sheet change increments session_id and calls on_restart_required().
    Speed/run/loop changes keep the same session_id so writer continues from current row.
    """
    st.sidebar.header("Streaming Control")

    config = read_stream_config()
    dataset_files = list_dataset_files()

    if not dataset_files:
        st.sidebar.warning("No .csv/.xlsx/.xls files found in datasets/ or project folder.")
        selected_file = str(config.get("source_file", DEFAULT_STREAM_CONFIG["source_file"]))
    else:
        current_file_name = Path(str(config.get("source_file", dataset_files[0]))).name
        default_index = dataset_files.index(current_file_name) if current_file_name in dataset_files else 0
        selected_file = st.sidebar.selectbox("Dataset file", dataset_files, index=default_index)

    selected_extension = Path(selected_file).suffix.lower()
    current_sheet = config.get("source_sheet", 3)
    selected_sheet = current_sheet

    if selected_extension in (".xlsx", ".xls"):
        sheet_names = get_excel_sheet_options(selected_file)
        if sheet_names:
            sheet_labels = [f"{index + 1}: {name}" for index, name in enumerate(sheet_names)]
            default_sheet_number = 3
            if isinstance(current_sheet, int) or str(current_sheet).isdigit():
                default_sheet_number = int(current_sheet)
            elif str(current_sheet) in sheet_names:
                default_sheet_number = sheet_names.index(str(current_sheet)) + 1
            default_sheet_index = min(max(default_sheet_number - 1, 0), len(sheet_labels) - 1)
            selected_sheet_label = st.sidebar.selectbox("Excel sheet", sheet_labels, index=default_sheet_index)
            selected_sheet = int(selected_sheet_label.split(":", 1)[0])
        else:
            selected_sheet = st.sidebar.number_input("Excel sheet number", min_value=1, value=3, step=1)
    else:
        selected_sheet = config.get("source_sheet", 3)

    speed_values = list(SPEED_OPTIONS.values())
    current_speed = float(config.get("delay_sec", 5.0))
    default_speed_index = speed_values.index(current_speed) if current_speed in speed_values else 0
    selected_speed_label = st.sidebar.selectbox("Writing speed", list(SPEED_OPTIONS.keys()), index=default_speed_index)
    selected_speed = SPEED_OPTIONS[selected_speed_label]

    running = st.sidebar.checkbox("Run writer", value=bool(config.get("running", True)))
    loop = st.sidebar.checkbox("Loop at end of file", value=bool(config.get("loop", False)))

    current_source_name = Path(str(config.get("source_file", ""))).name
    dataset_changed = selected_file != current_source_name
    sheet_changed = str(selected_sheet) != str(config.get("source_sheet", 3)) and selected_extension in (".xlsx", ".xls")
    restart_required = dataset_changed or sheet_changed

    if st.sidebar.button("Apply streaming settings", type="primary"):
        new_config = config.copy()
        new_config["source_file"] = selected_file
        new_config["live_file"] = DATA_FILE
        new_config["source_sheet"] = int(selected_sheet) if str(selected_sheet).isdigit() else selected_sheet
        new_config["header_row"] = int(config.get("header_row", 1))
        new_config["delay_sec"] = float(selected_speed)
        new_config["running"] = bool(running)
        new_config["loop"] = bool(loop)

        if restart_required:
            new_config["session_id"] = int(time.time())
            if on_restart_required is not None:
                on_restart_required()
        else:
            new_config["session_id"] = config.get("session_id", 1)

        write_json_atomic(CONFIG_FILE, new_config)
        st.sidebar.success("Streaming settings applied")
        config = new_config

    selected_patient_display = get_patient_display(selected_file)
    active_source_file = Path(str(config.get("source_file", selected_file))).name
    active_patient_display = get_patient_display(active_source_file)

    st.sidebar.caption(f"Selected in dropdown: {selected_patient_display}")
    st.sidebar.caption(f"Currently applied: {active_patient_display}")

    return active_source_file, active_patient_display, config
