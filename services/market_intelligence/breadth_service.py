
"""Validated NSE Market Breadth application service."""

import pandas as pd

from core.market_intelligence.breadth import analyze_market_breadth


REQUIRED_STOCK_FIELDS = {
    "Date",
    "Symbol",
    "Previous Close",
    "Current Close",
    "Source",
    "Exchange",
    "Timeframe",
    "Fallback Reason",
    "Fetched At UTC",
    "Validation Status",
}


def _validate_fetch_timestamps(values: pd.Series) -> pd.Series:
    """Require every fetch timestamp to be valid and timezone-aware."""

    validated = []

    for value in values:
        if pd.isna(value) or not str(value).strip():
            raise ValueError(
                "Every stock observation requires Fetched At UTC."
            )

        try:
            timestamp = pd.Timestamp(value)
        except (TypeError, ValueError, OverflowError):
            raise ValueError(
                "Stock observations contain an invalid Fetched At UTC."
            )

        if pd.isna(timestamp) or timestamp.tzinfo is None:
            raise ValueError(
                "Fetched At UTC must be timezone-aware."
            )

        validated.append(
            timestamp.tz_convert("UTC").isoformat().replace(
                "+00:00", "Z"
            )
        )

    return pd.Series(validated, index=values.index, dtype="string")


def analyze_nse_market_breadth(
    stock_data: pd.DataFrame,
    verified_universe: pd.DataFrame,
    observation_date,
):
    """Analyze NSE breadth with verified universe and full provenance."""

    if not isinstance(stock_data, pd.DataFrame):
        raise TypeError("stock_data must be a pandas DataFrame.")

    if stock_data.empty:
        raise ValueError("Stock observations are empty.")

    if not isinstance(verified_universe, pd.DataFrame):
        raise TypeError(
            "verified_universe must be a pandas DataFrame."
        )

    if verified_universe.empty:
        raise ValueError("Verified NSE universe is empty.")

    missing = REQUIRED_STOCK_FIELDS.difference(stock_data.columns)

    if missing:
        raise ValueError(
            "Stock data missing required fields: "
            + ", ".join(sorted(missing))
        )

    if "Universe Verification Status" not in verified_universe.columns:
        raise ValueError(
            "NSE universe verification status is missing."
        )

    statuses = (
        verified_universe["Universe Verification Status"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    if statuses.isna().any() or not statuses.eq("MII_DATED").all():
        raise ValueError(
            "Every universe row must have MII_DATED verification status."
        )

    observation = pd.to_datetime(
        observation_date,
        errors="coerce",
    )

    if pd.isna(observation):
        raise ValueError("A valid observation date is required.")

    observation = pd.Timestamp(observation).normalize()

    data = stock_data.copy()

    try:
        data["Date"] = pd.to_datetime(
            data["Date"],
            errors="coerce",
        )
        dates = data["Date"].dt.normalize()
    except (AttributeError, TypeError, ValueError):
        raise ValueError(
            "Stock observations contain invalid dates."
        )

    if dates.isna().any():
        raise ValueError(
            "Stock observations contain invalid dates."
        )

    if not dates.eq(observation).all():
        raise ValueError(
            "Every stock observation must match the requested date."
        )

    text_columns = (
        "Symbol",
        "Source",
        "Exchange",
        "Timeframe",
        "Fallback Reason",
        "Validation Status",
    )

    for column in text_columns:
        data[column] = (
            data[column].astype("string").str.strip()
        )

        if data[column].isna().any():
            raise ValueError(
                f"Stock observations contain missing {column} values."
            )

    if data["Symbol"].eq("").any():
        raise ValueError(
            "Stock observations contain blank symbols."
        )

    data["Symbol"] = data["Symbol"].str.upper()
    data["Source"] = data["Source"].str.upper()
    data["Exchange"] = data["Exchange"].str.upper()
    data["Timeframe"] = data["Timeframe"].str.lower()
    data["Validation Status"] = (
        data["Validation Status"].str.upper()
    )

    if not data["Source"].isin({"NSE", "YAHOO"}).all():
        raise ValueError("Unsupported stock data source.")

    if not data["Exchange"].eq("NSE").all():
        raise ValueError(
            "Only NSE stock observations are supported."
        )

    if not data["Timeframe"].eq("1d").all():
        raise ValueError(
            "Only daily stock observations are supported."
        )

    if not data["Validation Status"].eq("PASS").all():
        raise ValueError(
            "Stock data validation did not PASS."
        )

    data["Fetched At UTC"] = _validate_fetch_timestamps(
        data["Fetched At UTC"]
    )

    yahoo_rows = data["Source"].eq("YAHOO")

    if data.loc[yahoo_rows, "Fallback Reason"].eq("").any():
        raise ValueError(
            "Every Yahoo observation requires an NSE fallback reason."
        )

    result = analyze_market_breadth(
        stock_data=data[
            ["Symbol", "Previous Close", "Current Close"]
        ],
        verified_universe=verified_universe,
        observation_date=observation,
    )

    result["analysis_status"] = result["coverage_status"]
    result["data_sources"] = sorted(
        data["Source"].unique().tolist()
    )
    result["source_counts"] = (
        data["Source"].value_counts().to_dict()
    )
    result["yahoo_fallback_symbols"] = sorted(
        data.loc[yahoo_rows, "Symbol"].unique().tolist()
    )
    result["fetch_timestamps_utc"] = sorted(
        data["Fetched At UTC"].unique().tolist()
    )

    return result
