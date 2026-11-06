"""
TradeLab Pro - Relative Strength Scanner Engine

NSE Primary market data with Yahoo Secondary fallback.
Official AMFI Market Cap filtering.
Multiple Main Benchmark comparisons.
Stock data is fetched once and reused.
Sector comparison is independently guarded.

BSE scanning remains disabled until its official universe
and validated data adapter are implemented.
"""

from datetime import timedelta

from data.market_data_adapter import fetch_market_history
from data.universe import (
    get_sector_symbols,
    load_nse_universe,
    validate_symbols_against_universe,
    validate_sector_membership,
)
from data.market_cap import filter_by_market_cap
from data.benchmark_mapping import (
    MAIN_BENCHMARKS,
    get_sector_benchmark,
)
from core.rs_windows import build_windows
from rs_engine import compare_on_common_dates


BSE_SCANNER_DISABLED_MESSAGE = (
    "BSE Scanner বন্ধ রাখা হয়েছে: Official verified BSE universe "
    "এবং validated BSE data adapter এখনো সম্পন্ন হয়নি। "
    "Manual BSE Symbol-সহ কোনো BSE Symbol Yahoo Finance-এ "
    "পাঠানো হবে না।"
)

VALID_MARKET_CAP_FILTERS = {
    "All Market Caps",
    "Large Cap",
    "Mid Cap",
    "Small Cap",
}


def get_market_data(symbol, start_date, end_date, exchange):
    """Fetch data using NSE Primary and Yahoo Secondary."""
    return fetch_market_history(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval="1d",
        exchange=exchange,
    )


def _source_info(data):
    """Extract source and fallback information."""
    if data is None or data.empty:
        return {
            "source": "Unavailable",
            "fallback_reason": "",
        }

    source = "Unknown"
    fallback_reason = ""

    if "Source" in data.columns:
        values = data["Source"].dropna().unique()
        if len(values):
            source = str(values[0])

    if "Fallback Reason" in data.columns:
        values = data["Fallback Reason"].dropna().unique()
        if len(values):
            fallback_reason = str(values[0])

    return {
        "source": source,
        "fallback_reason": fallback_reason,
    }


def _eligible_symbols(universe):
    """Return verified NSE EQ symbols."""
    if universe is None or universe.empty:
        raise ValueError("Eligible NSE universe is empty.")

    required = {"Symbol", "ISIN", "Series"}
    missing = required.difference(universe.columns)

    if missing:
        raise ValueError(
            "NSE universe missing required columns: "
            + ", ".join(sorted(missing))
        )

    eligible = universe[
        (
            universe["Series"]
            .astype("string")
            .str.strip()
            .str.upper()
            == "EQ"
        )
        & universe["ISIN"].notna()
    ]

    return set(
        eligible["Symbol"]
        .dropna()
        .astype("string")
        .str.strip()
        .str.upper()
    )


def resolve_symbols(
    sector,
    manual_symbols,
    selected_symbols=None,
    universe=None,
    exchange="NSE",
    eligible_universe=None,
):
    """Resolve and validate scanner stock selection."""
    if exchange == "BSE":
        raise ValueError(BSE_SCANNER_DISABLED_MESSAGE)

    if exchange != "NSE":
        raise ValueError("Exchange must be NSE.")

    if universe is None:
        universe = load_nse_universe()

    validation_universe = (
        eligible_universe
        if eligible_universe is not None
        else universe
    )
    available_symbols = _eligible_symbols(validation_universe)

    if manual_symbols and manual_symbols.strip():
        requested = [
            item.strip().upper()
            for item in manual_symbols.replace("\n", ",").split(",")
            if item.strip()
        ]
        requested = list(dict.fromkeys(requested))
        source = "Manual selection"

    elif selected_symbols:
        requested = list(dict.fromkeys(
            str(item).strip().upper()
            for item in selected_symbols
            if str(item).strip()
        ))
        source = "Verified NSE Universe selection"

    else:
        requested = get_sector_symbols(
            sector,
            universe=universe,
        )
        requested = [
            symbol for symbol in requested
            if symbol in available_symbols
        ]
        source = "Live audited official sector membership"

    if not requested:
        raise ValueError(
            "নির্বাচিত Market Cap এবং Sector অনুযায়ী "
            "কোনো eligible Stock পাওয়া যায়নি।"
        )

    return validate_symbols_against_universe(
        requested,
        validation_universe,
    ), source


def _normalize_benchmark_names(benchmark_name, benchmark_names):
    """Validate and preserve requested benchmark order."""
    requested = benchmark_names

    if requested is None:
        requested = [benchmark_name]

    if isinstance(requested, str):
        requested = [requested]

    normalized = list(dict.fromkeys(
        str(name).strip()
        for name in requested
        if str(name).strip()
    ))

    if not normalized:
        raise ValueError("কমপক্ষে একটি Main Benchmark নির্বাচন করুন।")

    invalid = [
        name for name in normalized
        if name not in MAIN_BENCHMARKS
    ]

    if invalid:
        raise ValueError(
            "Invalid Main Benchmark selection: "
            + ", ".join(invalid)
        )

    return normalized


def execute_scanner(
    sector,
    manual_symbols,
    exchange,
    benchmark_name,
    sector_benchmark_symbol,
    start_date,
    end_date,
    custom_windows,
    selected_symbols=None,
    universe=None,
    market_cap_filter="All Market Caps",
    market_cap_universe=None,
    benchmark_names=None,
):
    """
    Run multiple Main Index comparisons and one guarded
    Sector comparison. Legacy benchmark_name is supported.
    """
    if exchange == "BSE":
        raise ValueError(BSE_SCANNER_DISABLED_MESSAGE)

    if exchange != "NSE":
        raise ValueError("Exchange must be NSE.")

    if market_cap_filter not in VALID_MARKET_CAP_FILTERS:
        raise ValueError("Invalid Market Cap selection.")

    selected_benchmarks = _normalize_benchmark_names(
        benchmark_name,
        benchmark_names,
    )

    if universe is None:
        universe = load_nse_universe()

    if market_cap_filter == "All Market Caps":
        eligible_universe = universe
    else:
        if market_cap_universe is None:
            raise ValueError(
                "Verified AMFI Market Cap data is required "
                "for the selected Market Cap filter."
            )

        eligible_universe = filter_by_market_cap(
            market_cap_universe,
            market_cap_filter,
        )

        if eligible_universe.empty:
            raise ValueError(
                f"No verified NSE stocks available for "
                f"{market_cap_filter}."
            )

    symbols, selection_source = resolve_symbols(
        sector=sector,
        manual_symbols=manual_symbols,
        selected_symbols=selected_symbols,
        universe=universe,
        exchange=exchange,
        eligible_universe=eligible_universe,
    )

    windows = build_windows(
        start_date,
        end_date,
        custom_windows,
    )
    fetch_start = start_date - timedelta(days=10)

    # Sector membership guard.
    sector_allowed, sector_reason = validate_sector_membership(
        sector,
        symbols,
        universe=universe,
    )

    configured_sector_benchmark = get_sector_benchmark(sector)

    if not configured_sector_benchmark:
        sector_allowed = False
        sector_reason = (
            f"No configured sector benchmark exists for {sector}."
        )
    elif sector_benchmark_symbol != configured_sector_benchmark:
        sector_allowed = False
        sector_reason = (
            "Selected sector benchmark does not match the configured "
            "sector benchmark."
        )

    # Fetch Main Benchmarks.
    benchmark_data = {}
    benchmark_sources = {}
    benchmark_errors = {}

    for name in selected_benchmarks:
        symbol = MAIN_BENCHMARKS[name]

        try:
            data = get_market_data(
                symbol,
                fetch_start,
                end_date,
                "NSE",
            )

            if data is None or data.empty:
                raise ValueError(
                    "Benchmark returned empty market data."
                )

            benchmark_data[name] = data
            benchmark_sources[name] = _source_info(data)

        except Exception as error:
            benchmark_errors[name] = str(error)
            benchmark_sources[name] = _source_info(None)

    # Fetch Sector Benchmark independently.
    sector_data = None
    sector_source = _source_info(None)

    if sector_allowed:
        try:
            sector_data = get_market_data(
                configured_sector_benchmark,
                fetch_start,
                end_date,
                "NSE",
            )

            if sector_data is None or sector_data.empty:
                raise ValueError(
                    "Sector benchmark returned empty data."
                )

            sector_source = _source_info(sector_data)

        except Exception as error:
            sector_data = None
            sector_reason = (
                "Sector benchmark data could not be fetched: "
                + str(error)
            )

    stock_data_cache = {}
    stock_sources = {}
    errors = []

    if sector_allowed and sector_data is None:
        errors.append({
            "Stock": "SECTOR INDEX",
            "Reason": sector_reason,
        })

    # Fetch every stock only once.
    for symbol in symbols:
        try:
            data = get_market_data(
                symbol,
                fetch_start,
                end_date,
                "NSE",
            )

            if data is None or data.empty:
                raise ValueError("Stock returned empty market data.")

            stock_data_cache[symbol] = data
            stock_sources[symbol] = _source_info(data)

        except Exception as error:
            errors.append({
                "Stock": symbol,
                "Reason": str(error),
            })

    main_results = []
    sector_results = []

    # Main Benchmark comparisons.
    for benchmark in selected_benchmarks:
        benchmark_frame = benchmark_data.get(benchmark)

        if benchmark_frame is None:
            continue

        benchmark_source = benchmark_sources[benchmark]

        for symbol, stock_data in stock_data_cache.items():
            stock_source = stock_sources[symbol]

            for window_name, dates in windows.items():
                window_start, window_end = dates

                try:
                    comparison = compare_on_common_dates(
                        stock_data=stock_data,
                        benchmark_data=benchmark_frame,
                        start_date=window_start,
                        end_date=window_end,
                    )

                    main_results.append({
                        "Benchmark": benchmark,
                        "Stock": symbol,
                        "Window": window_name,
                        "Stock Return (%)": round(
                            comparison["stock_return_pct"], 2
                        ),
                        "Main Index Return (%)": round(
                            comparison["benchmark_return_pct"], 2
                        ),
                        "Excess Return (%)": round(
                            comparison["stock_vs_benchmark_pct"], 2
                        ),
                        "Common Sessions": (
                            comparison["common_trading_sessions"]
                        ),
                        "Start Date": comparison["start_date"],
                        "End Date": comparison["end_date"],
                        "Stock Source": stock_source["source"],
                        "Main Index Source": benchmark_source["source"],
                        "Stock Fallback Reason": (
                            stock_source["fallback_reason"]
                        ),
                        "Main Index Fallback Reason": (
                            benchmark_source["fallback_reason"]
                        ),
                    })

                except Exception as error:
                    errors.append({
                        "Stock": symbol,
                        "Benchmark": benchmark,
                        "Window": window_name,
                        "Reason": str(error),
                    })

    # Sector comparisons remain separate.
    if sector_data is not None:
        for symbol, stock_data in stock_data_cache.items():
            stock_source = stock_sources[symbol]

            for window_name, dates in windows.items():
                window_start, window_end = dates

                try:
                    comparison = compare_on_common_dates(
                        stock_data=stock_data,
                        benchmark_data=sector_data,
                        start_date=window_start,
                        end_date=window_end,
                    )

                    sector_results.append({
                        "Stock": symbol,
                        "Window": window_name,
                        "Stock Return (%)": round(
                            comparison["stock_return_pct"], 2
                        ),
                        "Sector Return (%)": round(
                            comparison["benchmark_return_pct"], 2
                        ),
                        "Sector Excess Return (%)": round(
                            comparison["stock_vs_benchmark_pct"], 2
                        ),
                        "Common Sessions": (
                            comparison["common_trading_sessions"]
                        ),
                        "Start Date": comparison["start_date"],
                        "End Date": comparison["end_date"],
                        "Stock Source": stock_source["source"],
                        "Sector Index Source": sector_source["source"],
                        "Stock Fallback Reason": (
                            stock_source["fallback_reason"]
                        ),
                        "Sector Index Fallback Reason": (
                            sector_source["fallback_reason"]
                        ),
                    })

                except Exception as error:
                    errors.append({
                        "Stock": symbol,
                        "Benchmark": "SECTOR",
                        "Window": window_name,
                        "Reason": str(error),
                    })

    benchmark_error = None

    if benchmark_errors:
        benchmark_error = "; ".join(
            f"{name}: {reason}"
            for name, reason in benchmark_errors.items()
        )

    first_benchmark = selected_benchmarks[0]

    return {
        "main_results": main_results,
        "sector_results": sector_results,
        "errors": errors,
        "benchmark_error": benchmark_error,
        "benchmark_errors": benchmark_errors,
        "benchmark_names": selected_benchmarks,
        "benchmark_name": first_benchmark,
        "benchmark_sources": benchmark_sources,
        "sector": sector,
        "selection_source": selection_source,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "windows": list(windows.keys()),
        "symbols": symbols,
        "exchange": exchange,
        "market_cap_filter": market_cap_filter,
        "market_cap_verified_count": len(eligible_universe),
        "sector_comparison_available": (
            sector_data is not None and bool(sector_results)
        ),
        "sector_comparison_reason": sector_reason,
        "main_index_source": benchmark_sources.get(
            first_benchmark,
            _source_info(None),
        ),
        "sector_index_source": sector_source,
    }
    
