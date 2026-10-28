"""Relative Strength calculation and comparison functions."""
import pandas as pd

def calculate_return(start_price: float, end_price: float) -> float:
    """Return percentage change, expressed as percent (e.g. 5.0 means +5%)."""
    if start_price <= 0:
        raise ValueError("start_price must be greater than zero")
    return ((end_price / start_price) - 1.0) * 100.0


def relative_performance(stock_return_pct: float, benchmark_return_pct: float) -> float:
    """Percentage-point relative performance: stock return minus benchmark return."""
    return stock_return_pct - benchmark_return_pct



def calculate_period_return(
    data: pd.DataFrame,
    start_date,
    end_date,
) -> float:
    """
    Calculate percentage return between two dates using Close prices.

    For non-trading dates, use the latest available trading date
    on or before each requested date.
    """
    if data.empty:
        raise ValueError("data must not be empty")

    if "Date" not in data.columns or "Close" not in data.columns:
        raise ValueError("data must contain Date and Close columns")

    start_date = pd.Timestamp(start_date)
    end_date = pd.Timestamp(end_date)

    if end_date < start_date:
        raise ValueError("end_date must not be earlier than start_date")

    prices = data[["Date", "Close"]].copy()
    prices["Date"] = pd.to_datetime(prices["Date"], errors="raise")
    prices["Close"] = pd.to_numeric(prices["Close"], errors="raise")
    prices = prices.sort_values("Date")

    if prices["Date"].duplicated().any():
        raise ValueError("data must not contain duplicate dates")

    if prices["Close"].isna().any() or (prices["Close"] <= 0).any():
        raise ValueError("Close prices must be positive and non-missing")

    start_rows = prices[prices["Date"] <= start_date]
    end_rows = prices[prices["Date"] <= end_date]

    if start_rows.empty or end_rows.empty:
        raise ValueError("No trading data available on or before a requested date")

    start_close = float(start_rows.iloc[-1]["Close"])
    end_close = float(end_rows.iloc[-1]["Close"])

    return calculate_return(start_close, end_close)
    

def compare_stock_with_benchmark(
    stock_data,
    benchmark_data,
    start_date,
    end_date,
) -> dict:
    """Compare stock and benchmark returns over the same date range."""

    stock_return = calculate_period_return(
        stock_data, start_date, end_date
    )

    benchmark_return = calculate_period_return(
        benchmark_data, start_date, end_date
    )

    relative = relative_performance(
        stock_return, benchmark_return
    )

    return {
        "stock_return_pct": stock_return,
        "benchmark_return_pct": benchmark_return,
        "relative_performance_pct": relative,
    }
    

def compare_stock_with_sector(
    stock_data,
    sector_data,
    start_date,
    end_date,
) -> dict:
    """Compare stock returns with sector returns over the same period."""

    stock_return = calculate_period_return(
        stock_data, start_date, end_date
    )

    sector_return = calculate_period_return(
        sector_data, start_date, end_date
    )

    relative = relative_performance(
        stock_return, sector_return
    )

    return {
        "stock_return_pct": stock_return,
        "sector_return_pct": sector_return,
        "relative_performance_pct": relative,
    }
    

def calculate_return_windows(
    data,
    windows: dict,
) -> dict:
    """
    Calculate returns for multiple custom date windows.

    Example:
        windows = {
            "1M": ("2026-09-01", "2026-10-01"),
            "3M": ("2026-07-01", "2026-10-01"),
        }
    """
    results = {}

    for name, dates in windows.items():
        if len(dates) != 2:
            raise ValueError(
                f"Window '{name}' must contain start and end dates"
            )

        start_date, end_date = dates

        results[name] = calculate_period_return(
            data, start_date, end_date
        )

    return results
    

def calculate_trading_day_return(
    data,
    trading_days: int,
) -> float:
    """
    Calculate return using the first and last Close
    among the latest N available trading sessions.

    N sessions contain N Close prices and N-1 intervals.
    """
    if not isinstance(trading_days, int) or isinstance(trading_days, bool):
        raise ValueError("trading_days must be a positive integer")

    if trading_days < 2:
        raise ValueError("trading_days must be at least 2")

    if data.empty:
        raise ValueError("data must not be empty")

    if "Date" not in data.columns or "Close" not in data.columns:
        raise ValueError("data must contain Date and Close columns")

    prices = data[["Date", "Close"]].copy()
    prices["Date"] = pd.to_datetime(prices["Date"], errors="raise")
    prices["Close"] = pd.to_numeric(prices["Close"], errors="raise")
    prices = prices.sort_values("Date")

    if prices["Date"].duplicated().any():
        raise ValueError("data must not contain duplicate dates")

    if prices["Close"].isna().any() or (prices["Close"] <= 0).any():
        raise ValueError("Close prices must be positive and non-missing")

    if len(prices) < trading_days:
        raise ValueError("Not enough trading sessions in the data")

    selected = prices.tail(trading_days)

    return calculate_return(
        float(selected.iloc[0]["Close"]),
        float(selected.iloc[-1]["Close"]),
    )
    
