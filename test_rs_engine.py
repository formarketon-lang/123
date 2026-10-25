import pytest

from core.rs_engine import calculate_return, relative_performance


def test_calculate_return_positive():
    assert calculate_return(100, 110) == pytest.approx(10.0)


def test_calculate_return_negative():
    assert calculate_return(100, 90) == pytest.approx(-10.0)


def test_calculate_return_rejects_nonpositive_start():
    with pytest.raises(ValueError):
        calculate_return(0, 100)


def test_relative_performance():
    assert relative_performance(8.0, 5.0) == pytest.approx(3.0)
