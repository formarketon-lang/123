
"""TradeLab Pro - Relative Strength Calculation Engine.

NSE/BSE cash-market return and relative-performance calculations.
All relative-performance values are percentage-point differences.
"""

from __future__ import annotations

import pandas as pd


# ---------------------------------------------------------
# 1. Basic Return Calculations
# ---------------------------------------------------------

def calculate_return(start_price: float, end_price: float) -> float:
    """Calculate percentage return between two positive prices."""

    start_price = float(start_price)
    end_price = float(end_price)

    if start_price <= 0 or end_price <= 0:
        raise ValueError("Prices must be greater than zero.")

    return ((end_price / start_price) - 1.0) * 100.0


def relative_performance(
    stock_return_pct: float,
    benchmark_return_pct: float,
) -> float:
    """Stock return minus benchmark return, in percentage points."""

    return float(stock_return_pct) - float(benchmark_return_pct)


# ---------------------------------------------------------
# 2. Data Validation and Normalization
# ---------------------------------------------------------

def _normalize_price_data(data: pd.DataFrame, name: str) -> pd.DataFrame:
    """Validate and normalize Date and Close columns."""

    if not isinstance(data, pd.DataFrame):
        raise TypeError(f"{name} data must be a pandas DataFrame.")

    if data.empty:
        raise ValueError(f"{name} data must not be empty.")

    if not {"Date", "Close"}.issubset(data.columns):
        raise ValueError(f"{name} data must contain Date and Close columns.")

    prices = data[["Date", "Close"]].copy()

    prices["Date"] = pd.to_datetime(
        prices["Date"], errors="coerce"
    )

    prices["Close"] = pd.to_numeric(
        prices["Close"], errors="coerce"
    )

    if prices["Date"].isna().any():
        raise ValueError(f"{name} contains invalid dates.")

    if prices["Close"].isna().any():
        raise ValueError(f"{name} contains missing or invalid Close prices.")

    if (prices["Close"] <= 0).any():
        raise ValueError(f"{name} Close prices must be positive.")

    # Normalize timezone-aware dates to timezone-naive dates.
    if prices["Date"].dt.tz is not None:
        prices["Date"] = prices["Date"].dt.tz_localize(None)

    # Normalize to calendar dates.
    prices["Date"] = prices["Date"].dt.normalize()

    if prices["Date"].duplicated().any():
        raise ValueError(f"{name} contains duplicate trading dates.")

    return prices.sort_values("Date").reset_index(drop=True)


def _validate_date_range(start_date, end_date):
    """Validate requested analysis dates."""

    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)

    if start.tzinfo is not None:
        start = start.tz_localize(None)

    if end.tzinfo is not None:
        end = end.tz_localize(None)

    start = start.normalize()
    end = end.normalize()

    if end < start:
        raise ValueError("end_date must not be earlier than start_date.")

    return start, end


# ---------------------------------------------------------
# 3. Period Return
# ---------------------------------------------------------

def calculate_period_return(
    data: pd.DataFrame,
    start_date,
    end_date,
) -> float:
    """Calculate return using latest available Close on or before dates."""

    prices = _normalize_price_data(data, "Price")

    start, end = _validate_date_range(start_date, end_date)

    start_rows = prices[prices["Date"] <= start]
    end_rows = prices[prices["Date"] <= end]

    if start_rows.empty or end_rows.empty:
        raise ValueError(
            "No trading data available on or before a requested date."
        )

    start_close = float(start_rows.iloc[-1]["Close"])
    end_close = float(end_rows.iloc[-1]["Close"])

    return calculate_return(start_close, end_close)


# ---------------------------------------------------------
# 4. Stock vs Benchmark
# ---------------------------------------------------------

def compare_stock_with_benchmark(
    stock_data,
    benchmark_data,
    start_date,
    end_date,
) -> dict:
    """Compare stock and benchmark returns over a requested date range."""

    stock_return = calculate_period_return(
        stock_data, start_date, end_date
    )

    benchmark_return = calculate_period_return(
        benchmark_data, start_date, end_date
    )

    return {
        "stock_return_pct": stock_return,
        "benchmark_return_pct": benchmark_return,
        "relative_performance_pct": relative_performance(
            stock_return, benchmark_return
        ),
    }


# ---------------------------------------------------------
# 5. Stock vs Sector
# ---------------------------------------------------------

def compare_stock_with_sector(
    stock_data,
    sector_data,
    start_date,
    end_date,
) -> dict:
    """Compare stock and sector returns over a requested date range."""

    stock_return = calculate_period_return(
        stock_data, start_date, end_date
    )

    sector_return = calculate_period_return(
        sector_data, start_date, end_date
    )

    return {
        "stock_return_pct": stock_return,
        "sector_return_pct": sector_return,
        "relative_performance_pct": relative_performance(
            stock_return, sector_return
        ),
    }


# ---------------------------------------------------------
# 6. Stock vs Sector vs Benchmark
# ---------------------------------------------------------

def compare_stock_sector_benchmark(
    stock_data,
    sector_data,
    benchmark_data,
    start_date,
    end_date,
) -> dict:
    """Compare all three datasets using identical trading dates."""

    return compare_on_common_dates(
        stock_data=stock_data,
        benchmark_data=benchmark_data,
        start_date=start_date,
        end_date=end_date,
        sector_data=sector_data,
    )


# ---------------------------------------------------------
# 7. Custom Return Windows
# ---------------------------------------------------------

def calculate_return_windows(
    data: pd.DataFrame,
    windows: dict,
) -> dict:
    """Calculate returns for multiple custom date windows."""

    if not isinstance(windows, dict):
        raise TypeError("windows must be a dictionary.")

    results = {}

    for name, dates in windows.items():

        if not isinstance(dates, (tuple, list)) or len(dates) != 2:
            raise ValueError(
                f"Window '{name}' must contain start and end dates."
            )

        results[name] = calculate_period_return(
            data,
            dates[0],
            dates[1],
        )

    return results


# ---------------------------------------------------------
# 8. Trading Session Return
# ---------------------------------------------------------

def calculate_trading_day_return(
    data: pd.DataFrame,
    trading_days: int,
) -> float:
    """Calculate return over the latest N available trading sessions."""

    if (
        not isinstance(trading_days, int)
        or isinstance(trading_days, bool)
        or trading_days < 2
    ):
        raise ValueError("trading_days must be an integer of at least 2.")

    prices = _normalize_price_data(data, "Price")

    if len(prices) < trading_days:
        raise ValueError("Not enough trading sessions in the data.")

    selected = prices.tail(trading_days)

    return calculate_return(
        float(selected.iloc[0]["Close"]),
        float(selected.iloc[-1]["Close"]),
    )


# ---------------------------------------------------------
# 9. Trading Session Comparison
# ---------------------------------------------------------

def compare_trading_day_performance(
    stock_data,
    benchmark_data,
    trading_days: int,
    sector_data=None,
) -> dict:
    """Compare stock with benchmark and optionally its sector."""

    stock_return = calculate_trading_day_return(
        stock_data, trading_days
    )

    benchmark_return = calculate_trading_day_return(
        benchmark_data, trading_days
    )

    result = {
        "stock_return_pct": stock_return,
        "benchmark_return_pct": benchmark_return,
        "stock_vs_benchmark_pct": relative_performance(
            stock_return, benchmark_return
        ),
    }

    if sector_data is not None:

        sector_return = calculate_trading_day_return(
            sector_data, trading_days
        )

        result["sector_return_pct"] = sector_return

        result["stock_vs_sector_pct"] = relative_performance(
            stock_return, sector_return
        )

    return result


# ---------------------------------------------------------
# 10. Common Trading Date Comparison
# ---------------------------------------------------------

def compare_on_common_dates(
    stock_data,
    benchmark_data,
    start_date,
    end_date,
    sector_data=None,
) -> dict:
    """Compare stock, benchmark and optional sector on identical dates."""

    start, end = _validate_date_range(start_date, end_date)

    datasets = {
        "stock": stock_data,
        "benchmark": benchmark_data,
    }

    if sector_data is not None:
        datasets["sector"] = sector_data

    normalized = {
        name: _normalize_price_data(data, name)
        for name, data in datasets.items()
    }

    # Inner join ensures every dataset uses exactly the same dates.
    common = None

    for name, prices in normalized.items():

        series = prices.set_index("Date")["Close"].rename(name)

        if common is None:
            common = series.to_frame()
        else:
            common = common.join(series, how="inner")

    common = common.sort_index()

    common = common.loc[
        (common.index >= start) & (common.index <= end)
    ]

    if len(common) < 2:
        raise ValueError(
            "At least two common trading dates are required."
        )

    first = common.iloc[0]
    last = common.iloc[-1]

    stock_return = calculate_return(
        float(first["stock"]),
        float(last["stock"]),
    )

    benchmark_return = calculate_return(
        float(first["benchmark"]),
        float(last["benchmark"]),
    )

    result = {
        "start_date": common.index[0].strftime("%Y-%m-%d"),
        "end_date": common.index[-1].strftime("%Y-%m-%d"),
        "common_trading_sessions": len(common),
        "stock_return_pct": stock_return,
        "benchmark_return_pct": benchmark_return,
        "stock_vs_benchmark_pct": relative_performance(
            stock_return, benchmark_return
        ),
        "relative_performance_pct": relative_performance(
            stock_return, benchmark_return
        ),
    }

    if sector_data is not None:

        sector_return = calculate_return(
            float(first["sector"]),
            float(last["sector"]),
        )

        result["sector_return_pct"] = sector_return

        result["stock_vs_sector_pct"] = relative_performance(
            stock_return, sector_return
        )

    return result
