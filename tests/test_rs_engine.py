import pandas as pd
import pytest

from rs_engine import (
    calculate_return,
    relative_performance,
    calculate_period_return,
    compare_stock_with_benchmark,
    compare_stock_with_sector,
)


# --------------------------------------------------
# 1. Basic Return Calculation Tests
# --------------------------------------------------

def test_calculate_return_positive():
    assert calculate_return(100, 110) == pytest.approx(10.0)


def test_calculate_return_negative():
    assert calculate_return(100, 90) == pytest.approx(-10.0)


def test_calculate_return_rejects_nonpositive_start():
    with pytest.raises(ValueError):
        calculate_return(0, 100)


# --------------------------------------------------
# 2. Relative Performance Tests
# --------------------------------------------------

def test_relative_performance():
    assert relative_performance(8.0, 5.0) == pytest.approx(3.0)


# --------------------------------------------------
# 3. Date-Based Return Calculation Tests
# --------------------------------------------------

def test_calculate_period_return():
    data = pd.DataFrame({
        "Date": ["2026-10-01", "2026-10-05", "2026-10-10"],
        "Close": [100, 105, 110],
    })

    result = calculate_period_return(
        data,
        "2026-10-01",
        "2026-10-10",
    )

    assert result == pytest.approx(10.0)


def test_calculate_period_return_uses_previous_trading_day():
    data = pd.DataFrame({
        "Date": ["2026-10-01", "2026-10-05", "2026-10-10"],
        "Close": [100, 105, 110],
    })

    result = calculate_period_return(
        data,
        "2026-10-03",
        "2026-10-10",
    )

    assert result == pytest.approx(10.0)


def test_calculate_period_return_rejects_reversed_dates():
    data = pd.DataFrame({
        "Date": ["2026-10-01", "2026-10-10"],
        "Close": [100, 110],
    })

    with pytest.raises(ValueError):
        calculate_period_return(
            data,
            "2026-10-10",
            "2026-10-01",
        )


def test_calculate_period_return_rejects_empty_data():
    data = pd.DataFrame(columns=["Date", "Close"])

    with pytest.raises(ValueError):
        calculate_period_return(
            data,
            "2026-10-01",
            "2026-10-10",
        )


# --------------------------------------------------
# 4. Stock vs Benchmark Comparison Tests
# --------------------------------------------------

def test_compare_stock_with_benchmark():
    stock_data = pd.DataFrame({
        "Date": ["2026-10-01", "2026-10-10"],
        "Close": [100, 112],
    })

    benchmark_data = pd.DataFrame({
        "Date": ["2026-10-01", "2026-10-10"],
        "Close": [100, 108],
    })

    result = compare_stock_with_benchmark(
        stock_data,
        benchmark_data,
        "2026-10-01",
        "2026-10-10",
    )

    assert result["stock_return_pct"] == pytest.approx(12.0)
    assert result["benchmark_return_pct"] == pytest.approx(8.0)
    assert result["relative_performance_pct"] == pytest.approx(4.0)


# --------------------------------------------------
# 5. Stock vs Sector Comparison Tests
# --------------------------------------------------

def test_compare_stock_with_sector():
    stock_data = pd.DataFrame({
        "Date": ["2026-10-01", "2026-10-10"],
        "Close": [100, 115],
    })

    sector_data = pd.DataFrame({
        "Date": ["2026-10-01", "2026-10-10"],
        "Close": [100, 110],
    })

    result = compare_stock_with_sector(
        stock_data,
        sector_data,
        "2026-10-01",
        "2026-10-10",
    )

    assert result["stock_return_pct"] == pytest.approx(15.0)
    assert result["sector_return_pct"] == pytest.approx(10.0)
    assert result["relative_performance_pct"] == pytest.approx(5.0)


from rs_engine import calculate_return_windows


def test_calculate_return_windows():
    data = pd.DataFrame({
        "Date": [
            "2026-10-01",
            "2026-10-05",
            "2026-10-10",
            "2026-10-15",
        ],
        "Close": [100, 105, 110, 120],
    })

    windows = {
        "Window_A": ("2026-10-01", "2026-10-10"),
        "Window_B": ("2026-10-05", "2026-10-15"),
    }

    result = calculate_return_windows(data, windows)

    assert result["Window_A"] == pytest.approx(10.0)
    assert result["Window_B"] == pytest.approx(
        ((120 / 105) - 1) * 100
    )
    

from rs_engine import calculate_trading_day_return


def test_calculate_trading_day_return():
    data = pd.DataFrame({
        "Date": [
            "2026-10-01",
            "2026-10-05",
            "2026-10-10",
            "2026-10-15",
        ],
        "Close": [100, 102, 105, 110],
    })

    result = calculate_trading_day_return(data, 3)

    # Latest 3 sessions: 102, 105, 110
    assert result == pytest.approx(
        ((110 / 102) - 1) * 100
    )


def test_trading_day_return_rejects_insufficient_data():
    data = pd.DataFrame({
        "Date": ["2026-10-01", "2026-10-05"],
        "Close": [100, 105],
    })

    with pytest.raises(ValueError, match="Not enough trading sessions"):
        calculate_trading_day_return(data, 3)


def test_trading_day_return_rejects_one_session():
    data = pd.DataFrame({
        "Date": ["2026-10-01", "2026-10-05"],
        "Close": [100, 105],
    })

    with pytest.raises(ValueError, match="at least 2"):
        calculate_trading_day_return(data, 1)
        

from rs_engine import compare_trading_day_performance


def test_compare_trading_day_performance_with_sector():
    stock_data = pd.DataFrame({
        "Date": [
            "2026-10-01",
            "2026-10-05",
            "2026-10-10",
        ],
        "Close": [100, 105, 112],
    })

    benchmark_data = pd.DataFrame({
        "Date": [
            "2026-10-01",
            "2026-10-05",
            "2026-10-10",
        ],
        "Close": [100, 103, 107],
    })

    sector_data = pd.DataFrame({
        "Date": [
            "2026-10-01",
            "2026-10-05",
            "2026-10-10",
        ],
        "Close": [100, 104, 109],
    })

    result = compare_trading_day_performance(
        stock_data,
        benchmark_data,
        trading_days=3,
        sector_data=sector_data,
    )

    assert result["stock_return_pct"] == pytest.approx(12.0)
    assert result["benchmark_return_pct"] == pytest.approx(7.0)
    assert result["stock_vs_benchmark_pct"] == pytest.approx(5.0)
    assert result["sector_return_pct"] == pytest.approx(9.0)
    assert result["stock_vs_sector_pct"] == pytest.approx(3.0)


def test_compare_trading_day_performance_without_sector():
    data = pd.DataFrame({
        "Date": [
            "2026-10-01",
            "2026-10-05",
            "2026-10-10",
        ],
        "Close": [100, 105, 110],
    })

    result = compare_trading_day_performance(
        data, data, trading_days=3
    )

    assert result["stock_return_pct"] == pytest.approx(10.0)
    assert result["benchmark_return_pct"] == pytest.approx(10.0)
    assert result["stock_vs_benchmark_pct"] == pytest.approx(0.0)
    assert "sector_return_pct" not in result
    
