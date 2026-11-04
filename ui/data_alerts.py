"""
TradeLab Pro - Data Integrity Alerts
Displays the latest automated audit status.
"""

import json
from pathlib import Path

import streamlit as st


REPORT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "reports"
    / "data_integrity"
)


def _load_latest_audit():
    if not REPORT_ROOT.exists():
        return None

    report_files = sorted(
        REPORT_ROOT.glob("*/audit.json"),
        key=lambda path: path.parent.name,
        reverse=True,
    )

    for report_path in report_files:
        try:
            with report_path.open("r", encoding="utf-8") as file:
                records = json.load(file)

            if isinstance(records, list) and records:
                return report_path, records

        except (OSError, json.JSONDecodeError):
            continue

    return None


def render_data_integrity_alerts():
    latest = _load_latest_audit()

    if latest is None:
        st.info(
            "Data Integrity status unavailable. "
            "Please run the automated audit."
        )
        return

    report_path, records = latest

    flagged = [
        item for item in records
        if item.get("status") != "MATCH"
    ]

    audit_time = records[0].get(
        "audit_time_utc", "Unknown"
    )

    st.subheader("Data Integrity Monitor")

    if not flagged:
        st.success(
            "Data Integrity: All instruments MATCH."
        )
        st.caption(f"Latest audit (UTC): {audit_time}")
        return

    st.warning(
        f"{len(flagged)} of {len(records)} instruments "
        "require data review. Check before using affected "
        "data for analysis."
    )

    st.caption(
        f"Latest audit (UTC): {audit_time} | "
        f"Report: {report_path.parent.name}"
    )

    alert_rows = []

    for item in flagged:
        alert_rows.append({
            "Instrument": item.get("instrument", "Unknown"),
            "Status": item.get("status", "REVIEW"),
            "Common Sessions": item.get("common_sessions", 0),
            "NSE-only": item.get("nse_only_sessions", 0),
            "Yahoo-only": item.get("yahoo_only_sessions", 0),
            "OHLC Missing": item.get("ohlc_missing_sessions", 0),
            "OHLC Mismatch": item.get("ohlc_mismatch_sessions", 0),
            "Volume Mismatch": item.get("volume_mismatch_sessions", 0),
            "NSE Special Session Missing": item.get(
                "known_special_session_yahoo_missing", 0
            ),
            "Regular Session Missing": item.get(
                "known_regular_session_yahoo_missing", 0
            ),
        })

    st.dataframe(
        alert_rows,
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        "REVIEW indicates a detected source difference or "
        "data-quality condition. TradeLab Pro will not "
        "silently delete or modify market records."
      )
  
