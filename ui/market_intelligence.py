"""TradeLab Pro - Market Intelligence UI.

The page delegates all retrieval, validation and calculation to the
Market Intelligence service layer. It never fabricates market data.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from services.market_intelligence.bhavcopy_service import (
    analyze_nse_market_breadth_from_udiff,
)


def _default_trade_date() -> date:
    """Choose the previous weekday as a convenient initial date."""

    candidate = date.today() - timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate


def render_market_intelligence_page():
    """Render the NSE live breadth view with explicit REVIEW states."""

    st.header("Market Intelligence")

    st.caption(
        "TradeLab Pro · NSE Cash Market Intelligence"
    )

    st.info(
        "NSE UDiFF production downloader এবং official schema mapping "
        "যাচাই করা হয়েছে। Live MII identity বা daily coverage অসম্পূর্ণ "
        "হলে ফলাফল REVIEW দেখাবে; unverified stock কখনো breadth "
        "calculation-এ অন্তর্ভুক্ত হবে না।"
    )

    st.subheader("Module Activation Status")
    st.warning(
        "REVIEW — NSE source ও schema verified; live Symbol/ISIN "
        "exceptions এবং incomplete MII coverage থাকলে analysis "
        "verified PASS হবে না। BSE analysis disabled."
    )

    st.subheader("Live NSE Market Breadth")
    observation_date = st.date_input(
        "Observation Date",
        value=_default_trade_date(),
        help="শুধু NSE trading date নির্বাচন করুন।",
    )

    if not st.button("Run NSE Market Breadth"):
        st.caption(
            "তারিখ নির্বাচন করে Run চাপলে official NSE UDiFF ও "
            "same-date MII data যাচাই হবে।"
        )
        return

    try:
        result = analyze_nse_market_breadth_from_udiff(
            observation_date
        )
    except Exception as exc:
        st.error(
            "Market Breadth unavailable — verified data পাওয়া যায়নি: "
            f"{type(exc).__name__}: {exc}"
        )
        return

    status = result["analysis_status"]
    if status == "PASS":
        st.success(
            "PASS — source, schema, identity এবং coverage gates passed."
        )
    else:
        st.warning(
            "REVIEW — নিচের metrics verified full-universe result নয়। "
            "Unverified rows বাদ দেওয়া হয়েছে এবং missing members "
            "unchanged হিসেবে গণনা করা হয়নি।"
        )

    reconciliation = result["reconciliation"]
    breadth = result["breadth"]
    audit = result["audit"]

    st.write(f"Observation Date: {result['observation_date']}")
    st.write(f"Data Source: {result['source']} / NSE")
    st.write(f"Fetched At UTC: {result['fetched_at_utc']}")
    st.write(f"Archive SHA-256: {result['source_sha256']}")
    st.write(
        "MII Coverage: "
        f"{reconciliation['coverage_pct']}% "
        f"({reconciliation['observed_symbols']} / "
        f"{reconciliation['expected_symbols']})"
    )
    st.write(
        "Identity Status: "
        f"{reconciliation['identity_status']}"
    )
    st.write(
        "Schema Mapping: "
        f"{audit['schema_mapping_status']}"
    )
    st.write(f"Audit Status: {audit['audit_status']}")

    st.subheader("Breadth Counts")
    st.write(f"Advancing: {breadth['advancing']}")
    st.write(f"Declining: {breadth['declining']}")
    st.write(f"Unchanged: {breadth['unchanged']}")
    st.write(
        "Coverage Status: "
        f"{breadth['coverage_status']}"
    )

    exceptions = reconciliation.get("identity_exceptions", [])
    if exceptions:
        st.subheader("Identity Exceptions — Excluded")
        st.dataframe(
            pd.DataFrame(exceptions),
            use_container_width=True,
            hide_index=True,
        )

    missing_symbols = reconciliation.get("missing_symbols", [])
    if missing_symbols:
        st.subheader("MII Members Without a Daily Observation")
        st.write(", ".join(missing_symbols))

    if audit.get("audit_reasons"):
        st.subheader("Audit Reasons")
        for reason in audit["audit_reasons"]:
            st.write(f"• {reason}")

    st.subheader("Planned Analysis Areas")
    for area in [
        "Market Regime Analysis",
        "Market Breadth",
        "Advance / Decline Analysis",
        "Sector Strength",
        "Index Participation",
        "Market Trend Classification",
        "News and Events Context",
    ]:
        st.write(f"• {area}")

    st.caption(
        "No fabricated signals. No unsupported sector mappings. "
        "No F&O Scanner. BSE remains disabled."
    )
