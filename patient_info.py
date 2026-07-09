"""
patient_info.py

Patient registry utilities.
Maps dataset filename to patient display text, for example:
1_arvind.xlsx -> Arvind 32Y/M
"""

from pathlib import Path

import pandas as pd

from config import PATIENT_REGISTRY_FILE


def normalize_column_name(column_name) -> str:
    """Normalize CSV column names so 'file name' and 'file_name' both work."""
    return str(column_name).strip().lower().replace(" ", "_")


def read_patient_registry() -> pd.DataFrame:
    """Read patient_registry.csv and normalize column names."""
    registry_path = Path(PATIENT_REGISTRY_FILE)
    if not registry_path.exists():
        return pd.DataFrame()

    try:
        registry = pd.read_csv(registry_path)
        registry.columns = [normalize_column_name(column) for column in registry.columns]
        return registry
    except Exception:
        return pd.DataFrame()


def get_patient_display(file_name: str) -> str:
    """Return patient display text for selected dataset file."""
    registry = read_patient_registry()

    if registry.empty or "file_name" not in registry.columns:
        return Path(file_name).stem.replace("_", " ").title()

    selected_name = Path(str(file_name)).name.strip().lower()
    registry_file_names = registry["file_name"].astype(str).str.strip().str.lower()
    matched_rows = registry[registry_file_names == selected_name]

    if matched_rows.empty:
        return Path(file_name).stem.replace("_", " ").title()

    row = matched_rows.iloc[0]

    if "display_name" in registry.columns and pd.notna(row.get("display_name")):
        return str(row.get("display_name"))

    patient_name = str(row.get("patient_name", Path(file_name).stem)).strip()
    age = str(row.get("age", "")).strip()
    gender = str(row.get("gender", "")).strip()

    if age and gender:
        return f"{patient_name} {age}Y/{gender}"
    if age:
        return f"{patient_name} {age}Y"
    if gender:
        return f"{patient_name} /{gender}"
    return patient_name
