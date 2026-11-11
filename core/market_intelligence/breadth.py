"""Market breadth calculations with explicit universe coverage."""

import math

import pandas as pd


def analyze_market_breadth(
    stock_data: pd.DataFrame,
    expected_universe_size: int | None = None,
) -> dict:
    """Count advancing, declining and unchanged stocks."""

    if not isinstance(stock_data, pd.DataFrame):
        raise TypeError("stock_data must be a pandas DataFrame.")

    if stock_data.empty:
        raise ValueError("stock_data is empty.")

    required = {"Symbol", "Previous Close", "Current Close"}
    missing = required.difference(stock_data.columns)

    if missing:
        raise ValueError(
            "Missing required columns: " + ", ".join(sorted(missing))
        )

    if expected_universe_size is not None:
        if (
            not isinstance(expected_universe_size, int)
            or isinstance(expected_universe_size, bool)
            or expected_universe_size < 1
        ):
            raise ValueError(
                "expected_universe_size must be a positive integer."
            )

        if len(stock_data) > expected_universe_size:
            raise ValueError(
                "Observed stocks exceed expected universe size."
            )

    data = stock_data[
        ["Symbol", "Previous Close", "Current Close"]
    ].copy()

    data["Symbol"] = (
        data["Symbol"].astype("string").str.strip().str.upper()
    )

    if data["Symbol"].isna().any() or data["Symbol"].eq("").any():
        raise ValueError("Every stock must have a valid Symbol.")

    if data["Symbol"].duplicated().any():
        raise ValueError("Duplicate stock symbols found.")

    for column in ["Previous Close", "Current Close"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")

        if data[column].isna().any():
            raise ValueError(f"Invalid values found in {column}.")

        if not all(math.isfinite(float(x)) for x in data[column]):
            raise ValueError(f"Non-finite values found in {column}.")

        if (data[column] <= 0).any():
            raise ValueError(f"{column} values must be positive.")

    advancing = int(
        (data["Current Close"] > data["Previous Close"]).sum()
    )
    declining = int(
        (data["Current Close"] < data["Previous Close"]).sum()
    )
    unchanged = int(
        (data["Current Close"] == data["Previous Close"]).sum()
    )

    observed = len(data)

    coverage_pct = None
    if expected_universe_size is not None:
        coverage_pct = (
            observed / expected_universe_size
        ) * 100.0

    coverage_status = (
        "PASS"
        if expected_universe_size is not None
        and observed == expected_universe_size
        else "REVIEW"
    )

    return {
        "advancing": advancing,
        "declining": declining,
        "unchanged": unchanged,
        "observed_stocks": observed,
        "expected_universe_size": expected_universe_size,
        "coverage_pct": coverage_pct,
        "net_advances": advancing - declining,
        "advance_decline_ratio": (
            advancing / declining if declining else None
        ),
        "coverage_status": coverage_status,
    }
