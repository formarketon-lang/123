"""
TradeLab Pro - Relative Strength Results

Independent rankings for each Main Benchmark and window.
Backward-compatible with historical single-benchmark results.
Sector comparison remains separately guarded.
CSV exports preserve benchmark identity.
"""

import pandas as pd
import streamlit as st


MAIN_SORT_COLUMN = "Excess Return (%)"
SECTOR_SORT_COLUMN = "Sector Excess Return (%)"

MAIN_REQUIRED_COLUMNS = [
    "Benchmark",
    "Stock",
    "Window",
    "Stock Return (%)",
    "Main Index Return (%)",
    "Excess Return (%)",
    "Common Sessions",
    "Start Date",
    "End Date",
]

SECTOR_REQUIRED_COLUMNS = [
    "Stock",
    "Window",
    "Stock Return (%)",
    "Sector Return (%)",
    "Sector Excess Return (%)",
    "Common Sessions",
    "Start Date",
    "End Date",
]


def _prepare_main_dataframe(data, result=None):
    """Normalize legacy and current Main Benchmark result columns."""
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data).copy()

    if "Benchmark" not in df.columns:
        df["Benchmark"] = "Main Benchmark"

    # Legacy result compatibility.
    if (
        "Main Index Return (%)" not in df.columns
        and "Benchmark Return (%)" in df.columns
    ):
        df["Main Index Return (%)"] = df["Benchmark Return (%)"]

    defaults = {
        "Common Sessions": 0,
        "Start Date": (
            result.get("start_date", "")
            if result else ""
        ),
        "End Date": (
            result.get("end_date", "")
            if result else ""
        ),
    }

    for column, default in defaults.items():
        if column not in df.columns:
            df[column] = default

    return df


def build_ranked_results(data, windows, sort_column):
    """Build independent ranking for each benchmark and window."""
    if data is None or len(data) == 0:
        return pd.DataFrame()

    df = pd.DataFrame(data).copy()

    if sort_column not in df.columns or "Window" not in df.columns:
        raise ValueError(
            f"Required ranking columns missing: {sort_column}, Window"
        )

    if sort_column == MAIN_SORT_COLUMN and "Benchmark" not in df.columns:
        df["Benchmark"] = "Main Benchmark"

    group_columns = []

    if "Benchmark" in df.columns:
        group_columns.append("Benchmark")

    group_columns.append("Window")
    ranked_parts = []

    group_values = (
        df[group_columns]
        .drop_duplicates()
        .to_dict("records")
    )

    for group in group_values:
        mask = pd.Series(True, index=df.index)

        for column, value in group.items():
            mask &= df[column] == value

        view = df.loc[mask].copy()

        view[sort_column] = pd.to_numeric(
            view[sort_column],
            errors="coerce",
        )

        view = view.dropna(subset=[sort_column])

        view = view.sort_values(
            sort_column,
            ascending=False,
            kind="stable",
        ).reset_index(drop=True)

        if view.empty:
            continue

        view.insert(0, "Rank", range(1, len(view) + 1))
        ranked_parts.append(view)

    if not ranked_parts:
        return pd.DataFrame()

    return pd.concat(ranked_parts, ignore_index=True)


def _display_main_results(result):
    """Display and export Main Benchmark rankings."""
    main_results = result.get("main_results", [])
    windows = result.get("windows", [])

    if not main_results:
        st.warning(
            "Main Index-এর সঙ্গে তুলনাযোগ্য ফলাফল পাওয়া যায়নি।"
        )
        return

    try:
        normalized = _prepare_main_dataframe(
            main_results,
            result,
        )

        ranked = build_ranked_results(
            normalized.to_dict("records"),
            windows,
            MAIN_SORT_COLUMN,
        )

        if ranked.empty:
            st.warning("Main Index Ranking তৈরি করা যায়নি।")
            return

        missing = [
            column for column in MAIN_REQUIRED_COLUMNS
            if column not in ranked.columns
        ]

        if missing:
            st.error(
                "Main Results-এ প্রয়োজনীয় ডেটা পাওয়া যায়নি: "
                + ", ".join(missing)
            )
            return

        benchmark_names = (
            result.get("benchmark_names")
            or ranked["Benchmark"].drop_duplicates().tolist()
        )

        for benchmark in benchmark_names:
            st.markdown(f"### {benchmark} Ranking")

            benchmark_view = ranked[
                ranked["Benchmark"] == benchmark
            ]

            for window_name in windows:
                view = benchmark_view[
                    benchmark_view["Window"] == window_name
                ].copy()

                if view.empty:
                    continue

                st.markdown(f"**{window_name}**")
                st.dataframe(
                    view,
                    use_container_width=True,
                    hide_index=True,
                )

        csv_data = ranked.to_csv(
            index=False
        ).encode("utf-8-sig")

        st.download_button(
            "Download Main Index CSV",
            data=csv_data,
            file_name="tradelab_main_index_rs.csv",
            mime="text/csv",
            key="rs_main_csv",
            on_click="ignore",
        )

    except ValueError as error:
        st.error(f"Main Ranking Error: {error}")


def _display_sector_results(result):
    """Display guarded Sector Comparison and CSV export."""
    sector_results = result.get("sector_results", [])

    sector_available = result.get(
        "sector_comparison_available",
        bool(sector_results),
    )

    sector_reason = str(
        result.get("sector_comparison_reason", "") or ""
    )

    if not sector_available:
        reason_lower = sector_reason.lower()

        membership_failed = (
            "unverified" in reason_lower
            or "not verified" in reason_lower
            or "membership is not verified" in reason_lower
        )

        if membership_failed:
            st.warning(
                "Sector Membership Guard: Sector Comparison বন্ধ। "
                "কারণ: " + sector_reason
            )
        else:
            st.info(
                "Sector Membership Guard: Membership যাচাই করা হয়েছে, "
                "কিন্তু তুলনাযোগ্য ফলাফল পাওয়া যায়নি।"
            )

        return

    if not sector_results:
        st.info(
            "Sector Membership Guard পাস করেছে, কিন্তু "
            "তুলনাযোগ্য ফলাফল পাওয়া যায়নি।"
        )
        return

    sector_df = pd.DataFrame(sector_results)

    missing = [
        column for column in SECTOR_REQUIRED_COLUMNS
        if column not in sector_df.columns
    ]

    if missing:
        st.error(
            "Sector Results-এ প্রয়োজনীয় ডেটা পাওয়া যায়নি: "
            + ", ".join(missing)
        )
        return

    try:
        ranked = build_ranked_results(
            sector_results,
            result.get("windows", []),
            SECTOR_SORT_COLUMN,
        )

        if ranked.empty:
            st.warning("Sector Ranking তৈরি করা যায়নি।")
            return

        for window_name in result.get("windows", []):
            view = ranked[
                ranked["Window"] == window_name
            ].copy()

            if view.empty:
                continue

            st.markdown(f"**{window_name} Sector Ranking**")

            st.caption(
                "Actual Comparison Period: "
                f"{view['Start Date'].iloc[0]} to "
                f"{view['End Date'].iloc[0]}"
            )

            st.dataframe(
                view[["Rank"] + SECTOR_REQUIRED_COLUMNS],
                use_container_width=True,
                hide_index=True,
            )

        csv_data = ranked.to_csv(
            index=False
        ).encode("utf-8-sig")

        st.download_button(
            "Download Sector Comparison CSV",
            data=csv_data,
            file_name="tradelab_sector_rs.csv",
            mime="text/csv",
            key="rs_sector_csv",
            on_click="ignore",
        )

    except ValueError as error:
        st.error(f"Sector Ranking Error: {error}")


def display_results(result):
    """Render Main Benchmark and guarded Sector results."""
    st.divider()
    st.subheader("Stock vs Main Benchmarks")

    benchmark_names = (
        result.get("benchmark_names")
        or [result.get("benchmark_name", "Main Benchmark")]
    )

    st.write(
        f"**Sector:** {result.get('sector')}  \n"
        f"**Selection:** {result.get('selection_source')}  \n"
        f"**Main Benchmarks:** {', '.join(benchmark_names)}  \n"
        f"**Last Run Period:** {result.get('start_date')} to "
        f"{result.get('end_date')}"
    )

    benchmark_errors = result.get("benchmark_errors", {})

    if benchmark_errors:
        st.error(
            "এক বা একাধিক Main Benchmark-এর Data পাওয়া যায়নি।"
        )

        st.dataframe(
            pd.DataFrame([
                {
                    "Benchmark": name,
                    "Reason": reason,
                }
                for name, reason in benchmark_errors.items()
            ]),
            use_container_width=True,
            hide_index=True,
        )

    elif result.get("benchmark_error"):
        st.error(
            "Main Benchmark Data পাওয়া যায়নি: "
            + str(result["benchmark_error"])
        )

    _display_main_results(result)

    st.divider()
    st.subheader("Stock vs Sector Index")

    _display_sector_results(result)

    errors = result.get("errors", [])

    if errors:
        st.divider()
        st.subheader("Data Retrieval / Comparison Errors")

        st.dataframe(
            pd.DataFrame(errors),
            use_container_width=True,
            hide_index=True,
        )

    st.caption(
        "Excess Return = Stock Return − Benchmark Return. "
        "এটি percentage-point difference, ভবিষ্যৎ Return-এর পূর্বাভাস নয়।"
    )
