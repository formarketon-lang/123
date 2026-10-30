"""
TradeLab Pro - Relative Strength Scanner Engine

Handles market data retrieval and stock comparisons.
"""

from datetime import timedelta

from data.yahoo_adapter import fetch_yahoo_history
from data.universe import get_sector_symbols
from data.benchmark_mapping import MAIN_BENCHMARKS
from core.rs_windows import build_windows
from rs_engine import compare_on_common_dates


def get_market_data(symbol, start_date, end_date, exchange):
    """Fetch historical market data."""

    return fetch_yahoo_history(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval="1d",
        exchange=exchange,
    )


def resolve_symbols(sector, manual_symbols):
    """Resolve manually entered or configured stock symbols."""

    if manual_symbols and manual_symbols.strip():

        symbols = [
            item.strip().upper()
            for item in manual_symbols.replace("\n", ",").split(",")
            if item.strip()
        ]

        symbols = list(dict.fromkeys(symbols))

        return symbols, "Manual selection"

    symbols = get_sector_symbols(sector)

    if symbols:
        return symbols, "Configured starter universe"

    raise ValueError(
        "এই Sector-এর Stock Universe এখনো তৈরি হয়নি। "
        "Manual Stock Symbol লিখুন।"
    )


def execute_scanner(
    sector,
    manual_symbols,
    exchange,
    benchmark_name,
    sector_benchmark_symbol,
    start_date,
    end_date,
    custom_windows,
):
    """Run the complete Relative Strength analysis."""

    symbols, selection_source = resolve_symbols(
        sector,
        manual_symbols,
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

    # Fetch main benchmark.
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

    # Fetch sector benchmark.
    sector_data = None

    if sector_benchmark_symbol:
        try:
            sector_data = get_market_data(
                sector_benchmark_symbol,
                fetch_start,
                end_date,
                "NSE",
            )
        except Exception as error:
            errors.append({
                "Stock": "SECTOR INDEX",
                "Reason": str(error),
            })

    # Process each stock.
    if main_benchmark_data is not None:

        for symbol in symbols:

            try:
                stock_data = get_market_data(
                    symbol,
                    fetch_start,
                    end_date,
                    exchange,
                )

                for window_name, dates in windows.items():

                    window_start, window_end = dates

                    # Stock vs Main Index
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

                    # Stock vs Sector Index
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
    }
    
