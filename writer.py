"""
writer.py

Real-time data streamer for cerebral autoregulation / CPPopt monitoring.

Purpose
-------
This writer reads the selected patient source file from stream_config.json
and writes it row-by-row into live_data.csv. The dashboard reads live_data.csv
as the simulated real-time monitor feed.

Supported source files
----------------------
1. CSV files: .csv
2. Excel files: .xlsx, .xls

Important design
----------------
- Dashboard will change stream_config.json.
- Writer continuously watches stream_config.json.
- When dataset/sheet/session changes, writer resets live_data.csv.
- When only delay_sec changes, writer changes speed without needing restart.
"""

import csv
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd


# =========================================================
# FILES AND DEFAULT SETTINGS
# =========================================================

CONFIG_FILE = Path("stream_config.json")
DEFAULT_DATASET_FOLDER = Path("datasets")

DEFAULT_CONFIG: Dict[str, Any] = {
    "source_file": "1_arvind.xlsx",      # Can be CSV or Excel. Also searched inside datasets/.
    "live_file": "live_data.csv",        # Output file continuously read by dashboard.
    "source_sheet": 3,                    # For Excel only. Integer means 1-based sheet number; 3 = third sheet.
    "header_row": 1,                      # Header row number in source file; 1 means first row.
    "delay_sec": 5.0,                     # 5 sec = real monitor speed; 0.05 sec = fast testing.
    "running": True,                      # True = write rows, False = pause.
    "loop": False,                        # True = restart from beginning after end of file.
    "session_id": 1                       # Change this from dashboard to force restart from row 1.
}

REQUIRED_COLUMNS = ["TTDate", "TTTime", "mean1", "mean2"]
SUPPORTED_EXCEL_EXTENSIONS = {".xlsx", ".xls"}
SUPPORTED_CSV_EXTENSIONS = {".csv"}


# =========================================================
# CONFIG FUNCTIONS
# =========================================================

def create_default_config_if_missing() -> None:
    """Create stream_config.json if it does not exist."""
    if not CONFIG_FILE.exists():
        write_json_atomic(CONFIG_FILE, DEFAULT_CONFIG)
        print(f"Created default config: {CONFIG_FILE}")


def write_json_atomic(path: Path, data: Dict[str, Any]) -> None:
    """
    Write JSON safely using a temporary file and atomic replace.
    This prevents the writer from reading half-written JSON.
    """
    temp_path = path.with_suffix(path.suffix + ".tmp")

    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)

    os.replace(temp_path, path)


def read_config() -> Dict[str, Any]:
    """
    Read stream_config.json.
    Missing keys are filled from DEFAULT_CONFIG.
    """
    create_default_config_if_missing()

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as file:
            config = json.load(file)

        for key, value in DEFAULT_CONFIG.items():
            config.setdefault(key, value)

        return config

    except Exception as error:
        print(f"Config read error: {error}")
        return DEFAULT_CONFIG.copy()


# =========================================================
# SOURCE FILE FUNCTIONS
# =========================================================

def resolve_source_path(source_file: str) -> Path:
    """
    Resolve source file path.

    The dashboard may store either:
    - "1_arvind.xlsx"
    - "datasets/1_arvind.xlsx"
    - an absolute path

    This function supports all three.
    """
    candidate = Path(source_file)

    if candidate.exists():
        return candidate

    dataset_candidate = DEFAULT_DATASET_FOLDER / source_file

    if dataset_candidate.exists():
        return dataset_candidate

    raise FileNotFoundError(
        f"Source file not found: {source_file}. "
        f"Put it in the project folder or inside {DEFAULT_DATASET_FOLDER}/"
    )


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean dataframe before streaming.
    - Remove fully empty rows.
    - Strip spaces from column names.
    - Keep original columns, because dashboard may need monitor columns.
    """
    df = df.dropna(how="all").copy()
    df.columns = [str(column).strip() for column in df.columns]
    return df


def validate_required_columns(df: pd.DataFrame, source_path: Path) -> None:
    """
    Ensure source contains columns required by dashboard.
    Current dashboard requires:
    TTDate, TTTime, mean1, mean2
    """
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]

    if missing_columns:
        raise ValueError(
            f"Missing required columns in {source_path.name}: {missing_columns}. "
            f"Required columns are: {REQUIRED_COLUMNS}. "
            f"Available columns are: {list(df.columns)}"
        )


def excel_sheet_to_pandas_sheet_name(source_sheet: Any) -> Any:
    """
    Convert user-friendly Excel sheet setting to pandas sheet_name.

    In stream_config.json:
    - 3 means third sheet, because users count sheets from 1.
    - "Sheet3" means sheet named Sheet3.

    In pandas:
    - integer sheet index is 0-based.
    """
    if isinstance(source_sheet, int):
        return source_sheet - 1

    if isinstance(source_sheet, str):
        stripped = source_sheet.strip()

        if stripped.isdigit():
            return int(stripped) - 1

        return stripped

    return source_sheet


def read_source_dataframe(config: Dict[str, Any]) -> Tuple[pd.DataFrame, Path]:
    """
    Read source CSV or Excel file into a dataframe.
    """
    source_path = resolve_source_path(str(config["source_file"]))
    extension = source_path.suffix.lower()
    header_row = int(config.get("header_row", 1))
    pandas_header_index = header_row - 1

    if pandas_header_index < 0:
        raise ValueError("header_row must be 1 or greater")

    if extension in SUPPORTED_CSV_EXTENSIONS:
        df = pd.read_csv(source_path, header=pandas_header_index)

    elif extension in SUPPORTED_EXCEL_EXTENSIONS:
        pandas_sheet_name = excel_sheet_to_pandas_sheet_name(config.get("source_sheet", 3))
        df = pd.read_excel(source_path, sheet_name=pandas_sheet_name, header=pandas_header_index)

    else:
        raise ValueError(
            f"Unsupported source file type: {extension}. "
            f"Use CSV, XLSX, or XLS."
        )

    df = clean_dataframe(df)
    validate_required_columns(df, source_path)

    return df, source_path


# =========================================================
# LIVE CSV FUNCTIONS
# =========================================================

def reset_live_file(live_file: str, columns: List[str]) -> None:
    """
    Create a fresh live_data.csv with only the header.
    Called when a new source/session starts.
    """
    live_path = Path(live_file)

    if live_path.exists():
        live_path.unlink()

    with open(live_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(columns)

    print(f"Live file reset: {live_file}")


def append_live_row(live_file: str, row_values: List[Any]) -> None:
    """Append one monitor row to live_data.csv."""
    with open(live_file, "a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(row_values)


def dataframe_row_to_list(row: pd.Series) -> List[Any]:
    """
    Convert a dataframe row into CSV-safe values.
    Empty/NaN values are written as empty strings.
    """
    output = []

    for value in row.tolist():
        if pd.isna(value):
            output.append("")
        else:
            output.append(value)

    return output


# =========================================================
# SLEEP FUNCTION
# =========================================================

def smart_sleep(delay_sec: float) -> None:
    """
    Sleep in small chunks.
    This lets writer respond quickly when dashboard changes config.
    """
    delay_sec = max(float(delay_sec), 0.0)
    step = 0.2
    elapsed = 0.0

    while elapsed < delay_sec:
        sleep_now = min(step, delay_sec - elapsed)
        time.sleep(sleep_now)
        elapsed += sleep_now


# =========================================================
# MAIN LOOP
# =========================================================

def main() -> None:
    """
    Main writer loop.
    Keep this running in a separate terminal:

        python writer.py

    Dashboard can then control source file and writing speed using stream_config.json.
    """
    create_default_config_if_missing()

    current_restart_signature = None
    df = pd.DataFrame()
    source_path = None
    row_index = 0

    print("Writer started.")
    print("Waiting for dashboard/config instructions...")

    while True:
        config = read_config()

        source_file = str(config["source_file"])
        live_file = str(config["live_file"])
        source_sheet = config.get("source_sheet", 3)
        header_row = int(config.get("header_row", 1))
        delay_sec = float(config.get("delay_sec", 5.0))
        running = bool(config.get("running", True))
        loop = bool(config.get("loop", False))
        session_id = config.get("session_id", 1)

        # Dataset/sheet/session changes should restart the live stream from row 1.
        # delay_sec is intentionally not included, so speed can change without resetting.
        restart_signature = (source_file, live_file, str(source_sheet), header_row, session_id)

        if restart_signature != current_restart_signature:
            try:
                print("\nNew stream session detected")
                print(f"Source file : {source_file}")
                print(f"Excel sheet : {source_sheet}")
                print(f"Header row  : {header_row}")
                print(f"Live file   : {live_file}")
                print(f"Delay       : {delay_sec} sec")

                df, source_path = read_source_dataframe(config)
                reset_live_file(live_file, list(df.columns))

                row_index = 0
                current_restart_signature = restart_signature

                print(f"Loaded {len(df)} data rows from {source_path}")

            except Exception as error:
                print(f"Source loading error: {error}")
                current_restart_signature = None
                time.sleep(2)
                continue

        if not running:
            print("Writer paused. Set running=true from dashboard/config to continue.")
            time.sleep(1)
            continue

        if df.empty:
            print("No source data loaded yet.")
            time.sleep(1)
            continue

        if row_index >= len(df):
            if loop:
                print("End of source reached. Loop enabled, restarting from beginning.")
                reset_live_file(live_file, list(df.columns))
                row_index = 0
            else:
                print("End of source reached. Waiting...")
                time.sleep(2)
                continue

        row = df.iloc[row_index]
        row_values = dataframe_row_to_list(row)
        append_live_row(live_file, row_values)

        print(f"Written row {row_index + 1}/{len(df)}")
        row_index += 1

        # Speed can be changed from dashboard/config while writer is running.
        latest_config = read_config()
        latest_delay = float(latest_config.get("delay_sec", delay_sec))
        smart_sleep(latest_delay)


if __name__ == "__main__":
    main()
