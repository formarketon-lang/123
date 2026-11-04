"""Search the official NSE cash-equity security universe."""

from __future__ import annotations

import streamlit as st

from core.stock_search import search_stock_universe
from data.providers.nse_universe import fetch_nse_equity_universe


@st.cache_data(ttl=21600, show_spinner=False)
def load_nse_universe():
    """Cache the official NSE equity master for six hours."""
    return fetch_nse_equity_universe()


def render_stock_search_page():
    st.header("Stock Search")
    st.caption(
        "TradeLab Pro · Official NSE listed cash-equity universe"
    )

    st.info(
        "এই ধাপে NSE-এর EQ series security master ব্যবহার হচ্ছে। "
        "এটি listing search; Sector এবং Market Cap তথ্য এখানে অনুমান করে "
        "দেখানো হবে না। BSE universe পরবর্তী ধাপে যুক্ত হবে।"
    )

    refresh_col, status_col = st.columns([1, 2])

    with refresh_col:
        refresh = st.button(
            "Refresh NSE Universe",
            use_container_width=True,
        )

    if refresh:
        load_nse_universe.clear()

    try:
        with st.spinner("NSE official equity master লোড হচ্ছে..."):
            universe = load_nse_universe()

    except Exception as error:
        st.error(
            "NSE Stock Universe লোড করা যায়নি। "
            "NSE-এর সংযোগ বা CSV source সাময়িকভাবে unavailable হতে পারে।"
        )
        st.caption(f"Technical detail: {error}")

        if st.button("Retry NSE Connection"):
            load_nse_universe.clear()
            st.rerun()

        return

    with status_col:
        st.metric("NSE EQ Listed Securities", f"{len(universe):,}")

    query = st.text_input(
        "Search by Stock Symbol or Company Name",
        placeholder="যেমন: MARICO অথবা Marico Limited",
        key="stock_search_query",
    )

    matches = search_stock_universe(
        universe,
        query=query,
        limit=100,
    )

    st.caption(
        f"Search results: {len(matches):,} "
        "(সর্বোচ্চ 100টি ফলাফল দেখানো হচ্ছে)"
    )

    display_columns = [
        column
        for column in [
            "Symbol",
            "Company",
            "Series",
            "ISIN",
            "Listing Date",
            "Face Value",
            "Exchange",
            "Source",
        ]
        if column in matches.columns
    ]

    if matches.empty:
        st.warning("কোনো matching NSE stock পাওয়া যায়নি.")

    else:
        st.dataframe(
            matches[display_columns],
            use_container_width=True,
            hide_index=True,
        )
