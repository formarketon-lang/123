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
from services.market_intelligence.historical_ad_service import (\n    analyze_nse_historical_advance_decline,\n)\nfrom services.market_intelligence.regime_service import (
    SUPPORTED_NSE_INDEXES,
    analyze_index_market_regime,
)


def _default_trade_date() -> date:
    """Choose the previous weekday as a convenient initial date."""

    candidate = date.today() - timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate


def render_market_intelligence_page():
    """Render NSE regime and breadth views with explicit REVIEW states."""

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

    st.subheader("NSE Market Regime")
    benchmark = st.selectbox(
        "NSE Benchmark",
        options=list(SUPPORTED_NSE_INDEXES),
        format_func=lambda symbol: (
            f"{symbol} — {SUPPORTED_NSE_INDEXES[symbol]}"
        ),
        key="market_intelligence_regime_benchmark",
    )
    default_end = _default_trade_date()
    start_date = st.date_input(
        "Regime Start Date",
        value=default_end - timedelta(days=365),
        key="market_intelligence_regime_start",
    )
    end_date = st.date_input(
        "Regime End Date",
        value=default_end,
        key="market_intelligence_regime_end",
    )

    if st.button("Run NSE Market Regime"):
        try:
            regime_result = analyze_index_market_regime(
                benchmark,
                start_date,
                end_date,
            )
        except Exception as exc:
            st.error(
                "Market Regime unavailable — verified index data পাওয়া যায়নি: "
                f"{type(exc).__name__}: {exc}"
            )
        else:
            if regime_result["analysis_status"] == "PASS":
                st.success(
                    f"{regime_result['index_name']} Regime: "
                    f"{regime_result['regime']}"
                )
                st.write(
                    f"Close: {regime_result['close']:.2f}"
                )
                st.write(
                    f"Short SMA: {regime_result['short_sma']:.2f}"
                )
                st.write(
                    f"Long SMA: {regime_result['long_sma']:.2f}"
                )
                st.write(
                    f"Source: {regime_result['source']} / NSE"
                )
                st.write(
                    f"Fetched At UTC: {regime_result['fetched_at_utc']}"
                )
                if regime_result["fallback_reason"]:
                    st.write(
                        "Fallback Reason: "
                        f"{regime_result['fallback_reason']}"
                    )
            else:
                st.warning(
                    "REVIEW — verified Market Regime label প্রকাশ করা হয়নি."
                )

    st.divider()
    st.subheader("Live NSE Market Breadth")
    observation_date = st.date_input(
        "Breadth Observation Date",
        value=default_end,
        help="শুধু NSE trading date নির্বাচন করুন।",
        key="market_intelligence_breadth_date",
    )

    if st.button("Run NSE Market Breadth"):
        try:
            result = analyze_nse_market_breadth_from_udiff(
                observation_date
            )
        except Exception as exc:
            st.error(
                "Market Breadth unavailable — verified data পাওয়া যায়নি: "
                f"{type(exc).__name__}: {exc}"
            )
        else:
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

            exceptions = reconciliation.get(
                "identity_exceptions",
                [],
            )
            if exceptions:
                st.subheader("Identity Exceptions — Excluded")
                st.dataframe(
                    pd.DataFrame(exceptions),
                    use_container_width=True,
                    hide_index=True,
                )

            missing_symbols = reconciliation.get(
                "missing_symbols",
                [],
            )
            if missing_symbols:
                st.subheader("MII Members Without a Daily Observation")
                st.write(", ".join(missing_symbols))

            if audit.get("audit_reasons"):
                st.subheader("Audit Reasons")
                for reason in audit["audit_reasons"]:
                    st.write(f"• {reason}")

    st.divider()
    st.subheader("Historical Advance / Decline Analysis")
    st.warning(
        "শুধু verified NSE trading-session dates দিন। Official NSE calendar "
        "এখনও স্বয়ংক্রিয়ভাবে সংযুক্ত নয়; weekend/holiday নিজে থেকে অনুমান "
        "করা হবে না। সর্বোচ্চ ৩০টি session একবারে বিশ্লেষণ করা যাবে।"
    )
    session_text = st.text_input(
        "Verified NSE Sessions (YYYY-MM-DD, comma-separated)",
        value="",
        help="উদাহরণ: 2026-11-12, 2026-11-13, 2026-11-16",
        key="market_intelligence_historical_ad_sessions",
    )
    initial_anchor = st.number_input(
        "Cumulative A-D Initial Anchor",
        value=0,
        step=1,
        key="market_intelligence_historical_ad_anchor",
    )

    if st.button("Run Historical A/D Analysis"):
        try:
            tokens = [
                value.strip()
                for value in session_text.split(",")
                if value.strip()
            ]
            if not tokens:
                raise ValueError("কমপক্ষে একটি verified NSE session date দিন।")
            if len(tokens) > 30:
                raise ValueError("একবারে সর্বোচ্চ ৩০টি session date দেওয়া যাবে।")
            sessions = []
            for token in tokens:
                parsed = date.fromisoformat(token)
                if parsed.isoformat() != token:
                    raise ValueError(
                        f"Date অবশ্যই YYYY-MM-DD format-এ হতে হবে: {token}"
                    )
                sessions.append(parsed)

            historical_result = analyze_nse_historical_advance_decline(
                sessions,
                initial_anchor=int(initial_anchor),
            )
        except Exception as exc:
            st.error(
                "Historical A/D Analysis unavailable — "
                f"{type(exc).__name__}: {exc}"
            )
        else:
            status = historical_result["analysis_status"]
            if status == "PASS":
                st.success("PASS — requested sessions passed all available validation gates.")
            elif status == "BLOCKED":
                st.error("BLOCKED — contradictory or invalid source evidence detected.")
            elif status == "UNAVAILABLE":
                st.warning("UNAVAILABLE — one or more required NSE observations are unavailable.")
            else:
                st.warning(
                    "REVIEW — incomplete coverage or missing sessions detected. "
                    "The cumulative line is segmented; no missing data is filled."
                )

            st.write(
                f"Sessions: {historical_result['date_count']} | "
                f"PASS: {historical_result['pass_count']} | "
                f"REVIEW: {historical_result['review_count']} | "
                f"BLOCKED: {historical_result['blocked_count']} | "
                f"UNAVAILABLE: {historical_result['unavailable_count']} | "
                f"MISSING: {historical_result['missing_count']}"
            )
            st.subheader("Historical A/D Daily Metrics")
            st.dataframe(
                historical_result["per_date_status"],
                use_container_width=True,
                hide_index=True,
            )
            st.subheader("Cumulative A-D Line")
            line_data = historical_result["per_date_status"]
            if line_data["cumulative_ad"].notna().any():
                st.line_chart(
                    line_data,
                    x="observation_date",
                    y="cumulative_ad",
                )
            else:
                st.info("No verified PASS segment is available to plot.")
            st.subheader("Coverage and Validation")
            st.dataframe(
                historical_result["coverage"],
                use_container_width=True,
                hide_index=True,
            )
            st.subheader("Source and MII Provenance")
            st.dataframe(
                historical_result["provenance"],
                use_container_width=True,
                hide_index=True,
            )

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
