"""
ui/theme.py

All CSS styling for the Streamlit dashboard.
Change font sizes, colors, card dimensions, and dark-mode compatible styling here.
"""

import streamlit as st


def load_css() -> None:
    """Inject dashboard CSS into the Streamlit page."""
    st.markdown(
        """
        <style>
        .main-title {
            font-size: 42px;
            font-weight: 900;
            color: var(--text-color);
            margin-bottom: 4px;
            line-height: 1.15;
        }

        .subtitle {
            font-size: 18px;
            color: var(--text-color);
            opacity: 0.75;
            margin-bottom: 18px;
        }

        .patient-box {
            border: 1px solid #d0d7de;
            border-radius: 14px;
            padding: 12px 16px;
            background-color: rgba(255,255,255,0.10);
            min-height: 82px;
            text-align: right;
            box-shadow: 0 1px 2px rgba(0,0,0,0.06);
        }

        .patient-title {
            font-size: 16px;
            font-weight: 800;
            color: var(--text-color);
            opacity: 0.75;
            margin-bottom: 4px;
        }

        .patient-value {
            font-size: 30px;
            font-weight: 900;
            color: var(--text-color);
            line-height: 1.05;
        }

        .patient-file {
            font-size: 13px;
            font-weight: 700;
            color: var(--text-color);
            opacity: 0.65;
            margin-top: 4px;
        }

        .metric-card {
            border: 1px solid #d0d7de;
            border-radius: 12px;
            padding: 18px 18px;
            background-color: white;
            box-shadow: 0 1px 2px rgba(0,0,0,0.06);
            min-height: 138px;
        }

        .metric-label {
            font-size: 30px;
            font-weight: 900;
            color: #111827;
            margin-bottom: 8px;
            line-height: 1.05;
        }

        .metric-value {
            font-size: 56px;
            font-weight: 900;
            line-height: 1.0;
            letter-spacing: -1px;
        }

        .metric-sub {
            font-size: 17px;
            color: #475569;
            margin-top: 8px;
            font-weight: 700;
        }

        .side-value-card {
            border: 1px solid #d0d7de;
            border-radius: 14px;
            padding: 24px 18px;
            background-color: white;
            min-height: 300px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.06);
        }

        .side-title {
            font-size: 32px;
            font-weight: 900;
            margin-bottom: 10px;
            line-height: 1.05;
        }

        .side-value {
            font-size: 64px;
            font-weight: 900;
            margin-bottom: 12px;
            line-height: 1.0;
            letter-spacing: -1px;
        }

        .side-caption {
            font-size: 17px;
            color: #475569;
            font-weight: 700;
        }

        .auto-good {
            margin-top: 14px;
            padding: 14px;
            border-radius: 10px;
            background-color: #dcfce7;
            color: #166534;
            font-size: 24px;
            font-weight: 900;
            text-align: center;
            border: 2px solid #22c55e;
        }

        .auto-bad {
            margin-top: 14px;
            padding: 14px;
            border-radius: 10px;
            background-color: #fee2e2;
            color: #991b1b;
            font-size: 24px;
            font-weight: 900;
            text-align: center;
            border: 2px solid #ef4444;
        }

        .auto-na {
            margin-top: 14px;
            padding: 14px;
            border-radius: 10px;
            background-color: #f1f5f9;
            color: #475569;
            font-size: 24px;
            font-weight: 900;
            text-align: center;
            border: 2px solid #94a3b8;
        }

        h2, h3 {
            color: var(--text-color) !important;
            font-weight: 900 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
