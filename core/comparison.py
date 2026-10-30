
import pandas as pd

from core.validation import normalize_price_data, validate_date_range
from core.returns import calculate_return, relative_performance


def _build_common_data(datasets):
    """Join datasets using identical trading dates."""

    common = None

    for name, data in datasets.items():
        prices = normalize_price_data(data, name)

        series = (
            prices.set_index("Date")["Close"]
            .rename(name)
        )

        if common is None:
            common = series.to_frame()
        else:
            common = common.join(series, how="inner")

    return common.sort_index()


def compare_on_common_dates(
    stock_data,
    benchmark_data,
    start_date,
    end_date,
    sector_data=None,
) -> dict:
    """Compare stock, benchmark and optional sector on common dates."""

    start, end = validate_date_range(start_date, end_date)

    datasets = {
        "stock": stock_data,
        "benchmark": benchmark_data,
    }

    if sector_data is not None:
        datasets["sector"] = sector_data

    common = _build_common_data(datasets)

    common = common.loc[
        (common.index >= start) & (common.index <= end)
    ]

    if len(common) < 2:
        raise ValueError(
            "At least two common trading dates are required "
            "within the requested date range."
        )

    first = common.iloc[0]
    last = common.iloc[-1]

    stock_return = calculate_return(
        first["stock"], last["stock"]
    )

    benchmark_return = calculate_return(
        first["benchmark"], last["benchmark"]
    )

    relative_pct = relative_performance(
        stock_return, benchmark_return
    )

    result = {
        "start_date": common.index[0].strftime("%Y-%m-%d"),
        "end_date": common.index[-1].strftime("%Y-%m-%d"),
        "common_trading_sessions": len(common),
        "stock_return_pct": stock_return,
        "benchmark_return_pct": benchmark_return,
        "stock_vs_benchmark_pct": relative_pct,
        "relative_performance_pct": relative_pct,
    }

    if sector_data is not None:
        sector_return = calculate_return(
            first["sector"], last["sector"]
        )

        result["sector_return_pct"] = sector_return
        result["stock_vs_sector_pct"] = relative_performance(
            stock_return, sector_return
        )

    return result


def compare_stock_with_benchmark(
    stock_data,
    benchmark_data,
    start_date,
    end_date,
) -> dict:
    """Compare stock against a main benchmark."""

    return compare_on_common_dates(
        stock_data,
        benchmark_data,
        start_date,
        end_date,
    )


def compare_stock_with_sector(
    stock_data,
    sector_data,
    start_date,
    end_date,
) -> dict:
    """Compare stock against its sector index."""

    result = compare_on_common_dates(
        stock_data,
        sector_data,
        start_date,
        end_date,
    )

    return {
        "start_date": result["start_date"],
        "end_date": result["end_date"],
        "common_trading_sessions": result["common_trading_sessions"],
        "stock_return_pct": result["stock_return_pct"],
        "sector_return_pct": result["benchmark_return_pct"],
        "relative_performance_pct": result["relative_performance_pct"],
        "stock_vs_sector_pct": result["relative_performance_pct"],
    }


def compare_stock_sector_benchmark(
    stock_data,
    sector_data,
    benchmark_data,
    start_date,
    end_date,
) -> dict:
    """Compare stock with sector and main benchmark."""

    return compare_on_common_dates(
        stock_data,
        benchmark_data,
        start_date,
        end_date,
        sector_data=sector_data,
    )


def compare_trading_day_performance(
    stock_data,
    benchmark_data,
    trading_days: int,
    sector_data=None,
) -> dict:
    """Compare latest N common trading sessions."""

    if (
        not isinstance(trading_days, int)
        or isinstance(trading_days, bool)
        or trading_days < 2
    ):
        raise ValueError(
            "trading_days must be an integer of at least 2."
        )

    datasets = {
        "stock": stock_data,
        "benchmark": benchmark_data,
    }

    if sector_data is not None:
        datasets["sector"] = sector_data

    common = _build_common_data(datasets)

    if len(common) < trading_days:
        raise ValueError(
            f"Only {len(common)} common sessions available; "
            f"{trading_days} required."
        )

    selected = common.tail(trading_days)

    first = selected.iloc[0]
    last = selected.iloc[-1]

    stock_return = calculate_return(
        first["stock"], last["stock"]
    )

    benchmark_return = calculate_return(
        first["benchmark"], last["benchmark"]
    )

    result = {
        "start_date": selected.index[0].strftime("%Y-%m-%d"),
        "end_date": selected.index[-1].strftime("%Y-%m-%d"),
        "common_trading_sessions": len(selected),
        "stock_return_pct": stock_return,
        "benchmark_return_pct": benchmark_return,
        "stock_vs_benchmark_pct": relative_performance(
            stock_return, benchmark_return
        ),
    }

    if sector_data is not None:
        sector_return = calculate_return(
            first["sector"], last["sector"]
        )

        result["sector_return_pct"] = sector_return
        result["stock_vs_sector_pct"] = relative_performance(
            stock_return, sector_return
        )

    return result
