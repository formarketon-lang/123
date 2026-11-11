"""Market breadth with point-in-time verified NSE universe coverage."""

import math

import pandas as pd


def _verified_nse_universe(universe: pd.DataFrame) -> set[str]:
    """Validate NSE MII EQ identity fields and return symbols."""

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
        raise ValueError(
            "Verified universe contains missing identity fields."
        )

    if not data["Series"].eq("EQ").all():
        raise ValueError(
            "Verified universe must contain NSE EQ securities only."
        )

    if not data["Exchange"].eq("NSE").all():
        raise ValueError(
            "Verified universe must contain NSE securities only."
        )

    if not data["Source"].str.contains("MII", regex=False).all():
        raise ValueError(
            "Verified universe requires official NSE MII source."
        )

    if not data["ISIN"].str.fullmatch(r"IN[A-Z0-9]{10}").all():
        raise ValueError(
            "Verified universe contains invalid ISIN values."
        )

    if data["Symbol"].duplicated().any():
        raise ValueError(
            "Verified universe contains duplicate symbols."
        )

    if data["ISIN"].duplicated().any():
        raise ValueError(
            "Verified universe contains duplicate ISIN values."
        )

    return set(data["Symbol"].tolist())


def _point_in_time_status(
    universe: pd.DataFrame,
    observation_date: object | None,
) -> tuple[str, str, pd.Timestamp | None, pd.Timestamp | None]:
    """Validate snapshot date against the breadth observation date."""

    if "Universe As Of Date" not in universe.columns:
        return (
            "REVIEW",
            "UNIVERSE_SNAPSHOT_DATE_MISSING",
            None,
            None,
        )

    if observation_date is None:
        return (
            "REVIEW",
            "OBSERVATION_DATE_MISSING",
            None,
            None,
        )

    observation = pd.to_datetime(
        observation_date,
        errors="coerce",
    )

    if pd.isna(observation):
        return (
            "REVIEW",
            "OBSERVATION_DATE_INVALID",
            None,
            None,
        )

    observation = pd.Timestamp(observation).normalize()

    snapshot_values = pd.to_datetime(
        universe["Universe As Of Date"],
        errors="coerce",
    ).dropna()

    if snapshot_values.empty:
        return (
            "REVIEW",
            "UNIVERSE_SNAPSHOT_DATE_MISSING",
            None,
            observation,
        )

    snapshot_dates = {
        pd.Timestamp(value).normalize()
        for value in snapshot_values.tolist()
    }

    if len(snapshot_dates) != 1:
        return (
            "REVIEW",
            "UNIVERSE_SNAPSHOT_DATE_INCONSISTENT",
            None,
            observation,
        )

    snapshot = next(iter(snapshot_dates))

    if snapshot > observation:
        raise ValueError(
            "Future NSE universe snapshot cannot be used for "
            "an earlier observation date."
        )

    if snapshot < observation:
        return (
            "REVIEW",
            "UNIVERSE_SNAPSHOT_DATE_NOT_ALIGNED",
            snapshot,
            observation,
        )

    return (
        "PASS",
        "UNIVERSE_SNAPSHOT_DATE_ALIGNED",
        snapshot,
        observation,
    )


def analyze_market_breadth(
    stock_data: pd.DataFrame,
    expected_universe_size: int | None = None,
    verified_universe: pd.DataFrame | None = None,
    observation_date: object | None = None,
) -> dict:
    """Count advancing, declining and unchanged stocks.

    A PASS requires:
    1. Official NSE MII EQ identity validation.
    2. Exact observed/verified symbol membership.
    3. One valid universe snapshot date.
    4. Snapshot date exactly equal to observation_date.

    Older snapshots are REVIEW until a documented historical
    point-in-time policy is approved.
    """

    if not isinstance(stock_data, pd.DataFrame):
        raise TypeError("stock_data must be a pandas DataFrame.")

    if stock_data.empty:
        raise ValueError("stock_data is empty.")

    required = {"Symbol", "Previous Close", "Current Close"}
    missing = required.difference(stock_data.columns)

    if missing:
        raise ValueError(
            "Missing required columns: "
            + ", ".join(sorted(missing))
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
        data[column] = pd.to_numeric(
            data[column],
            errors="coerce",
        )

        if data[column].isna().any():
            raise ValueError(f"Invalid values found in {column}.")

        if not all(
            math.isfinite(float(value))
            for value in data[column]
        ):
            raise ValueError(f"Non-finite values found in {column}.")

        if (data[column] <= 0).any():
            raise ValueError(f"{column} values must be positive.")

    observed_symbols = set(data["Symbol"].tolist())
    observed = len(observed_symbols)

    verified_symbols = None
    snapshot_status = "REVIEW"
    snapshot_reason = "VERIFIED_UNIVERSE_NOT_PROVIDED"
    snapshot_date = None
    observed_date = (
        pd.to_datetime(observation_date, errors="coerce")
        if observation_date is not None
        else None
    )

    if verified_universe is not None:
        verified_symbols = _verified_nse_universe(
            verified_universe
        )

        unexpected = sorted(
            observed_symbols - verified_symbols
        )

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

        (
            snapshot_status,
            snapshot_reason,
            snapshot_date,
            observed_date,
        ) = _point_in_time_status(
            verified_universe,
            observation_date,
        )

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
        "PASS"
        if membership_complete and snapshot_status == "PASS"
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
        "universe_verified": verified_symbols is not None,
        "membership_complete": membership_complete,
        "universe_snapshot_status": snapshot_status,
        "universe_snapshot_reason": snapshot_reason,
        "universe_as_of_date": (
            snapshot_date.date().isoformat()
            if snapshot_date is not None
            else None
        ),
        "observation_date": (
            observed_date.date().isoformat()
            if observed_date is not None
            and not pd.isna(observed_date)
            else None
        ),
        "coverage_status": coverage_status,
    }
