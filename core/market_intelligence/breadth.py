
"""Market breadth calculations with verified NSE universe coverage."""

import math

import pandas as pd


def _verified_nse_universe(universe: pd.DataFrame) -> set[str]:
    """Return symbols only from a structurally verified NSE MII EQ universe."""

    if not isinstance(universe, pd.DataFrame) or universe.empty:
        raise ValueError("Verified NSE universe is empty or invalid.")

    required = {"Symbol", "ISIN", "Series", "Exchange", "Source"}
    missing = required.difference(universe.columns)

    if missing:
        raise ValueError(
            "Verified universe missing columns: "
            + ", ".join(sorted(missing))
        )

    data = universe[list(required)].copy()

    for column in required:
        data[column] = (
            data[column].astype("string").str.strip()
        )

    data["Symbol"] = data["Symbol"].str.upper()
    data["ISIN"] = data["ISIN"].str.upper()
    data["Series"] = data["Series"].str.upper()
    data["Exchange"] = data["Exchange"].str.upper()
    data["Source"] = data["Source"].str.upper()

    if data.isna().any().any() or data.eq("").any().any():
        raise ValueError("Verified universe contains missing identity fields.")

    if not data["Series"].eq("EQ").all():
        raise ValueError("Verified universe must contain NSE EQ securities only.")

    if not data["Exchange"].eq("NSE").all():
        raise ValueError("Verified universe must contain NSE securities only.")

    if not data["Source"].str.contains("MII", regex=False).all():
        raise ValueError("Verified universe requires official NSE MII source.")

    if not data["ISIN"].str.fullmatch(r"IN[A-Z0-9]{10}").all():
        raise ValueError("Verified universe contains invalid ISIN values.")

    if data["Symbol"].duplicated().any():
        raise ValueError("Verified universe contains duplicate symbols.")

    if data["ISIN"].duplicated().any():
        raise ValueError("Verified universe contains duplicate ISIN values.")

    return set(data["Symbol"].tolist())


def analyze_market_breadth(
    stock_data: pd.DataFrame,
    expected_universe_size: int | None = None,
    verified_universe: pd.DataFrame | None = None,
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

    observed_symbols = set(data["Symbol"].tolist())
    observed = len(observed_symbols)

    verified_symbols = None
    if verified_universe is not None:
        verified_symbols = _verified_nse_universe(verified_universe)

        unexpected = sorted(observed_symbols - verified_symbols)
        if unexpected:
            raise ValueError(
                "Observed symbols are not in verified NSE universe: "
                + ", ".join(unexpected)
            )

        verified_size = len(verified_symbols)

        if (
            expected_universe_size is not None
            and expected_universe_size != verified_size
        ):
            raise ValueError(
                "expected_universe_size does not match verified universe."
            )

        expected_universe_size = verified_size

    advancing = int(
        (data["Current Close"] > data["Previous Close"]).sum()
    )
    declining = int(
        (data["Current Close"] < data["Previous Close"]).sum()
    )
    unchanged = int(
        (data["Current Close"] == data["Previous Close"]).sum()
    )

    coverage_pct = None
    if expected_universe_size is not None:
        coverage_pct = (
            observed / expected_universe_size
        ) * 100.0

    membership_complete = (
        verified_symbols is not None
        and observed_symbols == verified_symbols
    )

    coverage_status = (
        "PASS" if membership_complete else "REVIEW"
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
        "universe_verified": verified_symbols is not None,
        "membership_complete": membership_complete,
        "coverage_status": coverage_status,
        }
    
