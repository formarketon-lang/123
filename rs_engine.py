"""Relative Strength calculation and comparison functions."""


def calculate_return(start_price: float, end_price: float) -> float:
    """Return percentage change, expressed as percent (e.g. 5.0 means +5%)."""
    if start_price <= 0:
        raise ValueError("start_price must be greater than zero")
    return ((end_price / start_price) - 1.0) * 100.0


def relative_performance(stock_return_pct: float, benchmark_return_pct: float) -> float:
    """Percentage-point relative performance: stock return minus benchmark return."""
    return stock_return_pct - benchmark_return_pct
