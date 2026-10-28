import pandas as pd
import pytest

from rs_engine import (
    calculate_return,
    relative_performance,
    calculate_period_return,
)


def test_calculate_return_positive():
    assert calculate_return(100, 110) == pytest.approx(10.0)


def test_calculate_return_negative():
    assert calculate_return(100, 90) == pytest.approx(-10.0)


def test_calculate_return_rejects_nonpositive_start():
    with pytest.raises(ValueError):
        calculate_return(0, 100)


def test_relative_performance():
    assert relative_performance(8.0, 5.0) == pytest.approx(3.0)


def test_calculate_period_return():
    data = pd.DataFrame({
        "Date": ["2026-10-01", "2026-10-05", "2026-10-10"],
        "Close": [100, 105, 110],
    })

    result = calculate_period_return(
        data, "2026-10-01", "2026-10-10"
    )

    assert result == pytest.approx(10.0)


def test_calculate_period_return_uses_previous_trading_day():
    data = pd.DataFrame({
        "Date": ["2026-10-01", "2026-10-05", "2026-10-10"],
        "Close": [100, 105, 110],
    })

    result = calculate_period_return(
        data, "2026-10-03", "2026-10-10"
    )

    assert result == pytest.approx(10.0)


def test_calculate_period_return_rejects_reversed_dates():
    data = pd.DataFrame({
        "Date": ["2026-10-01", "2026-10-10"],
        "Close": [100, 110],
    })

    with pytest.raises(ValueError):
        calculate_period_return(
            data, "2026-10-10", "2026-10-01"
        )


def test_calculate_period_return_rejects_empty_data():
    data = pd.DataFrame(columns=["Date", "Close"])

    with pytest.raises(ValueError):
        calculate_period_return(
            data, "2026-10-01", "2026-10-10"
        )
        
