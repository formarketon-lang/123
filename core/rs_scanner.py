
"""
TradeLab Pro - Relative Strength Scanner Engine

NSE scanning requires verified NSE EQ universe.
BSE scanning remains disabled until its official universe
and validated data adapter are implemented.
"""

from datetime import timedelta

from data.yahoo_adapter import fetch_yahoo_history
from data.universe import (
    get_sector_symbols,
    load_nse_universe,
    validate_symbols_against_universe,
    validate_sector_membership,
)
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


def get_market_data(symbol, start_date, end_date, exchange):
    """Fetch historical daily market data."""
    return fetch_yahoo_history(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval="1d",
        exchange=exchange,
    )


def resolve_symbols(
    sector,
    manual_symbols,
    selected_symbols=None,
    universe=None,
    exchange="NSE",
):
    """Resolve and validate scanner stock selection."""

    if exchange == "BSE":
        raise ValueError(BSE_SCANNER_DISABLED_MESSAGE)

    if exchange != "NSE":
        raise ValueError("Exchange must be NSE.")

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
        if universe is None:
            universe = load_nse_universe()

        requested = get_sector_symbols(
            sector,
            universe=universe,
        )
        source = "Live audited official sector membership"

    if not requested:
        raise ValueError("কোনো Stock নির্বাচন করা হয়নি।")

    if universe is None:
        universe = load_nse_universe()

    requested = validate_symbols_against_universe(
        requested,
        universe,
    )

    return requested, source


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
):
    """Run NSE Main Index and guarded Sector comparisons."""

    # Critical fail-closed security guard.
    # Must execute before universe loading or market-data requests.
    if exchange == "BSE":
        raise ValueError(BSE_SCANNER_DISABLED_MESSAGE)

    if exchange != "NSE":
        raise ValueError("Exchange must be NSE.")

    if universe is None:
        universe = load_nse_universe()

    symbols, selection_source = resolve_symbols(
        sector=sector,
        manual_symbols=manual_symbols,
        selected_symbols=selected_symbols,
        universe=universe,
        exchange=exchange,
    )

    windows = build_windows(
        start_date,
        end_date,
        custom_windows,
    )

    if benchmark_name not in MAIN_BENCHMARKS:
        raise ValueError("Invalid Main Benchmark selection.")

    benchmark_symbol = MAIN_BENCHMARKS[benchmark_name]
    fetch_start = start_date - timedelta(days=10)

    main_results = []
    sector_results = []
    errors = []
    benchmark_error = None

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

    sector_data = None

    try:
        main_benchmark_data = get_market_data(
            benchmark_symbol,
            fetch_start,
            end_date,
            "NSE",
        )
    except Exception as error:
        main_benchmark_data = None
        benchmark_error = str(error)

    if sector_allowed:
        try:
            sector_data = get_market_data(
                configured_sector_benchmark,
                fetch_start,
                end_date,
                "NSE",
            )
        except Exception as error:
            sector_reason = (
                "Sector benchmark data could not be fetched: "
                + str(error)
            )
            errors.append({
                "Stock": "SECTOR INDEX",
                "Reason": str(error),
            })

    if main_benchmark_data is not None:
        for symbol in symbols:
            try:
                stock_data = get_market_data(
                    symbol,
                    fetch_start,
                    end_date,
                    "NSE",
                )

                for window_name, dates in windows.items():
                    window_start, window_end = dates

                    main_comparison = compare_on_common_dates(
                        stock_data=stock_data,
                        benchmark_data=main_benchmark_data,
                        start_date=window_start,
                        end_date=window_end,
                    )

                    main_results.append({
                        "Stock": symbol,
                        "Window": window_name,
                        "Stock Return (%)": round(
                            main_comparison["stock_return_pct"], 2
                        ),
                        "Main Index Return (%)": round(
                            main_comparison["benchmark_return_pct"], 2
                        ),
                        "Excess Return (%)": round(
                            main_comparison["stock_vs_benchmark_pct"], 2
                        ),
                        "Common Sessions": (
                            main_comparison["common_trading_sessions"]
                        ),
                        "Start Date": main_comparison["start_date"],
                        "End Date": main_comparison["end_date"],
                    })

                    if sector_data is not None:
                        sector_comparison = compare_on_common_dates(
                            stock_data=stock_data,
                            benchmark_data=sector_data,
                            start_date=window_start,
                            end_date=window_end,
                        )

                        sector_results.append({
                            "Stock": symbol,
                            "Window": window_name,
                            "Stock Return (%)": round(
                                sector_comparison["stock_return_pct"], 2
                            ),
                            "Sector Return (%)": round(
                                sector_comparison["benchmark_return_pct"], 2
                            ),
                            "Sector Excess Return (%)": round(
                                sector_comparison["stock_vs_benchmark_pct"], 2
                            ),
                            "Common Sessions": (
                                sector_comparison["common_trading_sessions"]
                            ),
                            "Start Date": sector_comparison["start_date"],
                            "End Date": sector_comparison["end_date"],
                        })

            except Exception as error:
                errors.append({
                    "Stock": symbol,
                    "Reason": str(error),
                })

    return {
        "main_results": main_results,
        "sector_results": sector_results,
        "errors": errors,
        "benchmark_error": benchmark_error,
        "sector": sector,
        "selection_source": selection_source,
        "benchmark_name": benchmark_name,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "windows": list(windows.keys()),
        "symbols": symbols,
        "exchange": exchange,
        "sector_comparison_available": (
            sector_data is not None and bool(sector_results)
        ),
        "sector_comparison_reason": sector_reason,
    }
