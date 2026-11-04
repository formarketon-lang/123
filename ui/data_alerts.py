
"""
TradeLab Pro - Data Integrity Action Center

Reads the latest audit summary and daily comparison.
Shows detected issues, recommended actions and audit rerun access.
"""

import json
from pathlib import Path

import pandas as pd
import streamlit as st


REPORT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "reports"
    / "data_integrity"
)

AUDIT_WORKFLOW_URL = (
    "https://github.com/formarketon-lang/123/"
    "actions/workflows/data-integrity-audit.yml"
)


ACTION_GUIDANCE = {
    "SPECIAL_NSE_SESSION_YAHOO_MISSING": (
        "Special NSE session",
        "Keep the NSE record. Verify the special session. "
        "Do not create a Yahoo record artificially.",
    ),
    "NSE_REGULAR_SESSION_YAHOO_MISSING": (
        "Yahoo data missing",
        "Retry the Yahoo data download and compare the same date again.",
    ),
    "NSE_SESSION_YAHOO_MISSING_UNVERIFIED": (
        "Trading date needs verification",
        "Verify the official NSE trading calendar before deciding "
        "whether the Yahoo record is missing.",
    ),
    "YAHOO_RECORD_ON_KNOWN_NSE_HOLIDAY": (
        "Yahoo holiday record",
        "Inspect the Yahoo record. Do not treat it automatically "
        "as an NSE trading session.",
    ),
    "YAHOO_ONLY_SESSION_UNVERIFIED": (
        "Yahoo-only date",
        "Verify the exchange calendar and inspect the source record.",
    ),
    "OHLC_DATA_MISSING": (
        "Price data missing",
        "Refresh the affected source and validate Open, High, Low and Close.",
    ),
    "OHLC_PRICE_DIFFERENCE": (
        "Price mismatch",
        "Compare the source values for this date before using the data.",
    ),
    "VOLUME_DIFFERENCE": (
        "Volume mismatch",
        "Recheck Volume from both sources. Do not replace missing Volume with zero.",
    ),
    "OHLC_MATCH_VOLUME_NOT_AVAILABLE": (
        "Volume not comparable",
        "OHLC is within tolerance, but Volume cannot be verified. "
        "Treat Volume-based conclusions cautiously.",
    ),
}


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
                return report_path.parent, records

        except (OSError, json.JSONDecodeError):
            continue

    return None


def _load_daily_details(report_dir):
    detail_path = report_dir / "daily_comparison.csv"

    if not detail_path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(detail_path)
    except (OSError, pd.errors.ParserError):
        return pd.DataFrame()


def render_data_integrity_alerts():
    st.subheader("Data Integrity Action Center")

    latest = _load_latest_audit()

    if latest is None:
        st.info(
            "No usable audit report found. "
            "Run the Data Integrity Audit first."
        )
        st.link_button(
            "Open GitHub Actions / Run Audit",
            AUDIT_WORKFLOW_URL,
            use_container_width=True,
        )
        return

    report_dir, records = latest
    summary = pd.DataFrame(records)
    details = _load_daily_details(report_dir)

    if summary.empty:
        st.error("The latest audit summary is empty.")
        return

    audit_time = records[0].get(
        "audit_time_utc", "Unknown"
    )

    flagged = [
        item for item in records
        if item.get("status") != "MATCH"
    ]

    st.caption(
        f"Latest audit: {audit_time} UTC | "
        f"Audit ID: {report_dir.name}"
    )

    # Overall status
    if not flagged:
        st.success(
            "All audited instruments passed the strict MATCH check."
        )
    else:
        st.warning(
            f"{len(flagged)} of {len(records)} instruments "
            "need review before affected data is used."
        )

    # Summary
    summary_columns = [
        "instrument",
        "status",
        "common_sessions",
        "nse_only_sessions",
        "yahoo_only_sessions",
        "ohlc_missing_sessions",
        "ohlc_mismatch_sessions",
        "volume_mismatch_sessions",
    ]

    available_columns = [
        column for column in summary_columns
        if column in summary.columns
    ]

    st.markdown("**Instrument Status**")
    st.dataframe(
        summary[available_columns],
        use_container_width=True,
        hide_index=True,
    )

    # Recommended actions
    st.markdown("**Recommended Actions**")

    if not flagged:
        st.write("No corrective action is currently required.")
    else:
        for item in flagged:
            instrument = item.get("instrument", "Unknown")

            with st.expander(
                f"{instrument} — {item.get('status', 'REVIEW')}"
            ):
                st.write(
                    f"Common sessions: "
                    f"{item.get('common_sessions', 0)}"
                )

                st.write(
                    f"NSE-only: {item.get('nse_only_sessions', 0)} | "
                    f"Yahoo-only: {item.get('yahoo_only_sessions', 0)}"
                )

                st.write(
                    f"OHLC missing: "
                    f"{item.get('ohlc_missing_sessions', 0)} | "
                    f"OHLC mismatch: "
                    f"{item.get('ohlc_mismatch_sessions', 0)} | "
                    f"Volume mismatch: "
                    f"{item.get('volume_mismatch_sessions', 0)}"
                )

                if not details.empty and "Instrument" in details.columns:
                    instrument_details = details[
                        details["Instrument"] == instrument
                    ].copy()

                    if "Session_Classification" in instrument_details.columns:
                        instrument_details = instrument_details[
                            ~instrument_details[
                                "Session_Classification"
                            ].isin([
                                "VERIFIED_MATCH",
                                "SPECIAL_NSE_SESSION_MATCHED",
                            ])
                        ]

                    if not instrument_details.empty:
                        display_columns = [
                            "Date",
                            "Session_Classification",
                            "Classification_Reason",
                            "Open_Difference",
                            "High_Difference",
                            "Low_Difference",
                            "Close_Difference",
                        ]

                        display_columns = [
                            column for column in display_columns
                            if column in instrument_details.columns
                        ]

                        st.markdown("**Affected dates and findings**")
                        st.dataframe(
                            instrument_details[display_columns],
                            use_container_width=True,
                            hide_index=True,
                        )

                        if "Session_Classification" in instrument_details.columns:
                            issue_types = (
                                instrument_details[
                                    "Session_Classification"
                                ]
                                .dropna()
                                .unique()
                            )

                            for issue in issue_types:
                                title, action = ACTION_GUIDANCE.get(
                                    issue,
                                    (
                                        "Manual review required",
                                        "Inspect the source records and "
                                        "verify the exchange calendar.",
                                    ),
                                )
                                st.markdown(f"**{title}:** {action}")

    # Workflow action
    st.divider()
    st.markdown("**Audit Action**")
    st.write(
        "After correcting or reviewing source data, run the "
        "automated audit again to generate a fresh report."
    )

    st.link_button(
        "Open GitHub Actions / Re-run Data Integrity Audit",
        AUDIT_WORKFLOW_URL,
        use_container_width=True,
    )

    st.caption(
        "The Action Center does not automatically delete or modify "
        "market data. A new audit must verify any correction."
        )
    
