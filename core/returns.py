
import numpy as np

from core.validation import (
    normalize_price_data,
    validate_date_range,
)


def calculate_return(start_price: float, end_price: float) -> float:
    """Calculate percentage return."""

    start_price = float(start_price)
    end_price = float(end_price)

    if not np.isfinite(start_price) or not np.isfinite(end_price):
        raise ValueError("Prices must be finite numbers.")

    if start_price <= 0 or end_price <= 0:
        raise ValueError("Prices must be greater than zero.")

    return ((end_price / start_price) - 1.0) * 100.0


def relative_performance(
    stock_return_pct: float,
    benchmark_return_pct: float,
) -> float:
    """Calculate excess return in percentage points."""

    stock_return_pct = float(stock_return_pct)
    benchmark_return_pct = float(benchmark_return_pct)

    if not np.isfinite(stock_return_pct) or not np.isfinite(
        benchmark_return_pct
    ):
        raise ValueError("Returns must be finite numbers.")

    return stock_return_pct - benchmark_return_pct


def calculate_period_return(data, start_date, end_date) -> float:
    """Calculate return using latest available Close on or before dates."""

    prices = normalize_price_data(data, "Price")
    start, end = validate_date_range(start_date, end_date)

    start_rows = prices[prices["Date"] <= start]
    end_rows = prices[prices["Date"] <= end]

    if start_rows.empty or end_rows.empty:
        raise ValueError("No trading data available for requested dates.")

    return calculate_return(
        start_rows.iloc[-1]["Close"],
        end_rows.iloc[-1]["Close"],
    )


def calculate_return_windows(data, windows: dict) -> dict:
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
            data, dates[0], dates[1]
        )

    return results


def calculate_trading_day_return(data, trading_days: int) -> float:
    """Calculate return over latest N available observations."""

    if (
        not isinstance(trading_days, int)
        or isinstance(trading_days, bool)
        or trading_days < 2
    ):
        raise ValueError("trading_days must be an integer of at least 2.")

    prices = normalize_price_data(data, "Price")

    if len(prices) < trading_days:
        raise ValueError("Not enough trading sessions in the data.")

    selected = prices.tail(trading_days)

    return calculate_return(
        selected.iloc[0]["Close"],
        selected.iloc[-1]["Close"],
  )
  
