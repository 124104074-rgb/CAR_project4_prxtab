"""
live_data_reader.py

Live CSV reading and timestamp parsing utilities.
"""

from datetime import datetime

import pandas as pd


def parse_timestamp(row) -> datetime:
    """Convert TTDate and TTTime columns into a Python datetime object."""
    date_text = str(row["TTDate"]).strip()
    time_text = str(row["TTTime"]).strip()
    timestamp_text = f"{date_text} {time_text}"

    formats = [
        "%d/%m/%Y %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    ]

    for time_format in formats:
        try:
            return datetime.strptime(timestamp_text, time_format)
        except ValueError:
            continue

    raise ValueError(f"Cannot parse TTDate and TTTime: {timestamp_text}")


def read_live_csv(file_path: str) -> pd.DataFrame:
    """Read live_data.csv."""
    return pd.read_csv(file_path)


def get_new_rows(df: pd.DataFrame, last_processed_row: int) -> pd.DataFrame:
    """Return newly appended rows from the live CSV."""
    return df.iloc[last_processed_row:]
