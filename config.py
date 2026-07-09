"""
config.py

Central configuration for the cerebral autoregulation dashboard.
Edit this file when you want to change paths, colors, speed options,
graph windows, or refresh timing.
"""

# =========================================================
# FILES AND FOLDERS
# =========================================================

DATA_FILE = "live_data.csv"
CONFIG_FILE = "stream_config.json"
PATIENT_REGISTRY_FILE = "patient_registry.csv"
DATASET_FOLDER = "datasets"
SUPPORTED_DATA_EXTENSIONS = (".csv", ".xlsx", ".xls")

# =========================================================
# REAL-TIME UPDATE SETTINGS
# =========================================================

PRX_UPDATE_INTERVAL_SEC = 60
PRX_AUTOREGULATION_THRESHOLD = 0.25
DASHBOARD_REFRESH_SEC = 1.0

MAX_CPP_GRAPH_POINTS = 50000
MAX_PRX_GRAPH_POINTS = 10000
MAX_CPPOPT_GRAPH_POINTS = 10000

# =========================================================
# COLORS
# =========================================================

CPP_COLOR = "#1f77b4"
PRX_COLOR = "#ff7f0e"
CPPOPT_COLOR = "#2ca02c"
DIFF_COLOR = "#7e57c2"
MAP_COLOR = "#0ea5e9"
ICP_COLOR = "#ef4444"
GOOD_COLOR = "#16a34a"
BAD_COLOR = "#dc2626"
NEUTRAL_COLOR = "#64748b"
TIME_COLOR = "#334155"

# =========================================================
# SIDEBAR OPTIONS
# =========================================================

WINDOW_OPTIONS = {
    "30 min": 30,
    "1 hour": 60,
    "2 hours": 120,
    "4 hours": 240,
    "6 hours": 360,
    "8 hours": 480,
}

SPEED_OPTIONS = {
    "5 sec (real monitor speed)": 5.0,
    "1 sec": 1.0,
    "0.5 sec": 0.5,
    "0.05 sec (fast testing)": 0.05,
}

DEFAULT_STREAM_CONFIG = {
    "source_file": "1_arvind.xlsx",
    "live_file": DATA_FILE,
    "source_sheet": 3,
    "header_row": 1,
    "delay_sec": 5.0,
    "running": True,
    "loop": False,
    "session_id": 1,
}
