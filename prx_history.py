"""
prx_history.py

Utility module for the PRx / autoregulation history tab.

This file is intentionally independent from Streamlit and from the PRx
calculation function. The PRx calculation should remain inside analysis_1.py.
This module starts working only after a PRx value has already been calculated.

Main jobs of this file:
1. Classify each valid PRx value as Good/Bad autoregulation.
2. Store PRx history records in a simple list of dictionaries.
3. Calculate total Good/Bad autoregulation duration.
4. Calculate current continuous Good/Bad autoregulation duration.
5. Support stopwatch-like tags and history-from-tag filtering.
6. Convert history/tags into pandas DataFrames for dashboard display.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

import math


# =========================================================
# DEFAULT SETTINGS
# =========================================================

DEFAULT_PRX_THRESHOLD = 0.25  # PRx < 0.25 = good/preserved autoregulation
DEFAULT_PRX_INTERVAL_SEC = 60  # PRx is produced every 60 monitor seconds

GOOD_STATUS = "Good"
BAD_STATUS = "Bad"
UNAVAILABLE_STATUS = "Not available"

HistoryRecord = Dict[str, Any]
TagRecord = Dict[str, Any]


# =========================================================
# BASIC HELPERS
# =========================================================

def is_valid_number(value: Any) -> bool:
    """
    Return True only when value is a real finite number.

    NaN, None, strings, and infinity are treated as invalid.
    """
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return False

    return math.isfinite(numeric_value)


def normalize_timestamp(timestamp: Union[datetime, str]) -> datetime:
    """
    Convert a timestamp into a datetime object.

    Accepted inputs:
    - datetime object
    - ISO-like string, for example: 2026-06-24 13:20:00
    - dd-mm-yyyy HH:MM:SS
    - dd/mm/yyyy HH:MM:SS
    - HH:MM:SS only, in which case today's date is used internally

    In your dashboard, you will usually pass the existing monitor datetime object,
    so this function is mainly for safety.
    """
    if isinstance(timestamp, datetime):
        return timestamp

    timestamp_text = str(timestamp).strip()

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%d-%m-%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%H:%M:%S",
    ]

    for fmt in formats:
        try:
            parsed_time = datetime.strptime(timestamp_text, fmt)

            # If only HH:MM:SS was supplied, Python gives year 1900.
            # Replace that with today's date to keep comparisons practical.
            if fmt == "%H:%M:%S":
                today = datetime.today()
                parsed_time = parsed_time.replace(
                    year=today.year,
                    month=today.month,
                    day=today.day,
                )

            return parsed_time
        except ValueError:
            continue

    raise ValueError(f"Could not parse timestamp: {timestamp}")


def format_duration(total_seconds: Union[int, float]) -> str:
    """
    Convert seconds into a readable duration string.

    Examples:
    - 45      -> 45 sec
    - 300     -> 5 min
    - 3900    -> 1 hr 5 min
    - 93720   -> 1 day 2 hr 2 min
    """
    if not is_valid_number(total_seconds):
        return "Not available"

    total_seconds = int(round(float(total_seconds)))

    if total_seconds < 0:
        total_seconds = 0

    days = total_seconds // 86400
    remainder = total_seconds % 86400
    hours = remainder // 3600
    remainder %= 3600
    minutes = remainder // 60
    seconds = remainder % 60

    parts = []

    if days > 0:
        parts.append(f"{days} day" if days == 1 else f"{days} days")

    if hours > 0:
        parts.append(f"{hours} hr")

    if minutes > 0:
        parts.append(f"{minutes} min")

    if len(parts) == 0:
        parts.append(f"{seconds} sec")

    return " ".join(parts)


# =========================================================
# PRx CLASSIFICATION
# =========================================================

def classify_prx(
    prx_value: Any,
    threshold: float = DEFAULT_PRX_THRESHOLD,
) -> str:
    """
    Classify PRx into only two clinical states.

    Good / Preserved:
        PRx < threshold

    Bad / Impaired:
        PRx >= threshold

    Invalid PRx:
        Not available
    """
    if not is_valid_number(prx_value):
        return UNAVAILABLE_STATUS

    prx_value = float(prx_value)

    if prx_value < threshold:
        return GOOD_STATUS

    return BAD_STATUS


def status_to_autoregulation_text(status: str) -> str:
    """
    Convert short status into dashboard-friendly text.
    """
    if status == GOOD_STATUS:
        return "Preserved autoregulation"

    if status == BAD_STATUS:
        return "Impaired autoregulation"

    return "Not available"


# =========================================================
# HISTORY STORAGE
# =========================================================

def create_prx_record(
    timestamp: Union[datetime, str],
    prx_value: Any,
    threshold: float = DEFAULT_PRX_THRESHOLD,
) -> Optional[HistoryRecord]:
    """
    Create one PRx history record.

    Returns None when PRx is invalid, because the PRx History tab is intended
    to track only valid Good/Bad autoregulation periods.
    """
    if not is_valid_number(prx_value):
        return None

    timestamp = normalize_timestamp(timestamp)
    prx_value = float(prx_value)
    status = classify_prx(prx_value, threshold)

    return {
        "timestamp": timestamp,
        "prx": prx_value,
        "status": status,
        "autoregulation": status_to_autoregulation_text(status),
    }


def add_prx_record(
    history: List[HistoryRecord],
    timestamp: Union[datetime, str],
    prx_value: Any,
    threshold: float = DEFAULT_PRX_THRESHOLD,
) -> Optional[HistoryRecord]:
    """
    Add one valid PRx point to history.

    This function mutates the supplied history list and also returns the record.

    Usage in dashboard:
        add_prx_record(st.session_state.prx_history_table, current_timestamp, prx_value)
    """
    record = create_prx_record(timestamp, prx_value, threshold)

    if record is None:
        return None

    history.append(record)
    return record


def sort_history(history: List[HistoryRecord]) -> List[HistoryRecord]:
    """
    Return PRx history sorted by timestamp.
    """
    return sorted(history, key=lambda item: item["timestamp"])


# =========================================================
# TAG / STOPWATCH FEATURES
# =========================================================

def add_tag(
    tags: List[TagRecord],
    timestamp: Union[datetime, str],
    label_prefix: str = "Tag",
) -> TagRecord:
    """
    Add a stopwatch-like tag at the given monitor timestamp.

    For now, tag stores only:
    - label
    - timestamp

    No notes are stored, as finalized in the project discussion.
    """
    timestamp = normalize_timestamp(timestamp)
    tag_number = len(tags) + 1

    tag = {
        "label": f"{label_prefix} {tag_number}",
        "timestamp": timestamp,
    }

    tags.append(tag)
    return tag


def get_tag_options(tags: List[TagRecord]) -> List[str]:
    """
    Return readable tag labels for a dashboard selectbox.

    The first option is always Full history.
    """
    options = ["Full history"]

    for tag in tags:
        tag_time = normalize_timestamp(tag["timestamp"])
        options.append(f"{tag['label']} - {tag_time.strftime('%H:%M:%S')}")

    return options


def get_tag_by_option(
    tags: List[TagRecord],
    selected_option: str,
) -> Optional[TagRecord]:
    """
    Convert selected dashboard option back into a tag record.

    Returns None for Full history.
    """
    if selected_option == "Full history":
        return None

    for tag in tags:
        tag_time = normalize_timestamp(tag["timestamp"])
        expected_option = f"{tag['label']} - {tag_time.strftime('%H:%M:%S')}"

        if selected_option == expected_option:
            return tag

    return None


def filter_history_from_tag(
    history: List[HistoryRecord],
    tag: Optional[Union[TagRecord, datetime, str]],
) -> List[HistoryRecord]:
    """
    Return PRx history from a selected tag time.

    If tag is None, full history is returned.
    """
    sorted_records = sort_history(history)

    if tag is None:
        return sorted_records

    if isinstance(tag, dict):
        tag_time = normalize_timestamp(tag["timestamp"])
    else:
        tag_time = normalize_timestamp(tag)

    return [record for record in sorted_records if record["timestamp"] >= tag_time]


# =========================================================
# DURATION AND SEGMENT CALCULATION
# =========================================================

def summarize_autoregulation_duration(
    history: List[HistoryRecord],
    interval_sec: float = DEFAULT_PRX_INTERVAL_SEC,
) -> Dict[str, Any]:
    """
    Calculate total Good and Bad autoregulation time.

    Since PRx is calculated every 60 seconds, each valid PRx point represents
    approximately one PRx interval.
    """
    good_count = 0
    bad_count = 0

    for record in history:
        status = record.get("status", UNAVAILABLE_STATUS)

        if status == GOOD_STATUS:
            good_count += 1
        elif status == BAD_STATUS:
            bad_count += 1

    good_seconds = good_count * interval_sec
    bad_seconds = bad_count * interval_sec
    total_seconds = good_seconds + bad_seconds

    if total_seconds > 0:
        good_percent = (good_seconds / total_seconds) * 100
        bad_percent = (bad_seconds / total_seconds) * 100
    else:
        good_percent = 0.0
        bad_percent = 0.0

    return {
        "good_count": good_count,
        "bad_count": bad_count,
        "good_seconds": good_seconds,
        "bad_seconds": bad_seconds,
        "total_seconds": total_seconds,
        "good_duration_text": format_duration(good_seconds),
        "bad_duration_text": format_duration(bad_seconds),
        "total_duration_text": format_duration(total_seconds),
        "good_percent": good_percent,
        "bad_percent": bad_percent,
    }


def get_status_segments(
    history: List[HistoryRecord],
    interval_sec: float = DEFAULT_PRX_INTERVAL_SEC,
) -> List[Dict[str, Any]]:
    """
    Compress PRx history into continuous Good/Bad segments.

    Example:
    Good from 13:20:00 to 13:24:00
    Bad  from 13:25:00 to 13:28:00
    Good from 13:29:00 to 13:35:00
    """
    sorted_records = sort_history(history)

    if len(sorted_records) == 0:
        return []

    segments: List[Dict[str, Any]] = []

    current_status = sorted_records[0]["status"]
    segment_start = sorted_records[0]["timestamp"]
    segment_count = 1
    previous_time = sorted_records[0]["timestamp"]

    for record in sorted_records[1:]:
        record_status = record["status"]
        record_time = record["timestamp"]

        same_status = record_status == current_status

        # If there is a large time break, start a new segment even if the status is same.
        # A tolerance of 1.5 intervals avoids false breaks due to small timing drift.
        time_gap = (record_time - previous_time).total_seconds()
        continuous_time = time_gap <= (interval_sec * 1.5)

        if same_status and continuous_time:
            segment_count += 1
        else:
            segment_end = previous_time + timedelta(seconds=interval_sec)
            duration_sec = segment_count * interval_sec

            segments.append(
                {
                    "status": current_status,
                    "autoregulation": status_to_autoregulation_text(current_status),
                    "start_time": segment_start,
                    "end_time": segment_end,
                    "duration_sec": duration_sec,
                    "duration_text": format_duration(duration_sec),
                }
            )

            current_status = record_status
            segment_start = record_time
            segment_count = 1

        previous_time = record_time

    # Add final segment
    segment_end = previous_time + timedelta(seconds=interval_sec)
    duration_sec = segment_count * interval_sec

    segments.append(
        {
            "status": current_status,
            "autoregulation": status_to_autoregulation_text(current_status),
            "start_time": segment_start,
            "end_time": segment_end,
            "duration_sec": duration_sec,
            "duration_text": format_duration(duration_sec),
        }
    )

    return segments


def get_current_continuous_state(
    history: List[HistoryRecord],
    interval_sec: float = DEFAULT_PRX_INTERVAL_SEC,
) -> Dict[str, Any]:
    """
    Return the current continuous autoregulation state.

    Example output:
    {
        "status": "Good",
        "autoregulation": "Preserved autoregulation",
        "since": datetime(...),
        "duration_sec": 240,
        "duration_text": "4 min"
    }
    """
    segments = get_status_segments(history, interval_sec)

    if len(segments) == 0:
        return {
            "status": UNAVAILABLE_STATUS,
            "autoregulation": "Not available",
            "since": None,
            "duration_sec": 0,
            "duration_text": "Not available",
        }

    latest_segment = segments[-1]

    return {
        "status": latest_segment["status"],
        "autoregulation": latest_segment["autoregulation"],
        "since": latest_segment["start_time"],
        "duration_sec": latest_segment["duration_sec"],
        "duration_text": latest_segment["duration_text"],
    }


# =========================================================
# DATAFRAME CONVERSION FOR DASHBOARD DISPLAY
# =========================================================

def history_to_dataframe(history: List[HistoryRecord]):
    """
    Convert PRx history into a pandas DataFrame.

    Import pandas inside this function so the core logic above can stay simple.
    """
    import pandas as pd

    if len(history) == 0:
        return pd.DataFrame(columns=["Time", "PRx", "Status", "Autoregulation"])

    sorted_records = sort_history(history)

    return pd.DataFrame(
        {
            "Time": [record["timestamp"] for record in sorted_records],
            "PRx": [record["prx"] for record in sorted_records],
            "Status": [record["status"] for record in sorted_records],
            "Autoregulation": [record["autoregulation"] for record in sorted_records],
        }
    )


def tags_to_dataframe(tags: List[TagRecord]):
    """
    Convert tag list into a pandas DataFrame for dashboard display.
    """
    import pandas as pd

    if len(tags) == 0:
        return pd.DataFrame(columns=["Tag", "Time"])

    return pd.DataFrame(
        {
            "Tag": [tag["label"] for tag in tags],
            "Time": [normalize_timestamp(tag["timestamp"]) for tag in tags],
        }
    )


def segments_to_dataframe(segments: List[Dict[str, Any]]):
    """
    Convert continuous Good/Bad segments into a pandas DataFrame.
    """
    import pandas as pd

    if len(segments) == 0:
        return pd.DataFrame(
            columns=["Status", "Autoregulation", "Start Time", "End Time", "Duration"]
        )

    return pd.DataFrame(
        {
            "Status": [segment["status"] for segment in segments],
            "Autoregulation": [segment["autoregulation"] for segment in segments],
            "Start Time": [segment["start_time"] for segment in segments],
            "End Time": [segment["end_time"] for segment in segments],
            "Duration": [segment["duration_text"] for segment in segments],
        }
    )
