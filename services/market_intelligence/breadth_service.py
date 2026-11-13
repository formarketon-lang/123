
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
    "Validation Status",
}


def analyze_nse_market_breadth(
    stock_data: pd.DataFrame,
    verified_universe: pd.DataFrame,
    observation_date,
):
    """Analyze breadth using validated NSE observations and MII universe."""

    if not isinstance(stock_data, pd.DataFrame):
        raise TypeError("stock_data must be a pandas DataFrame.")

    if stock_data.empty:
        raise ValueError("Stock observations are empty.")

    if not isinstance(verified_universe, pd.DataFrame):
        raise TypeError("verified_universe must be a pandas DataFrame.")

    if verified_universe.empty:
        raise ValueError("Verified NSE universe is empty.")

    missing = REQUIRED_STOCK_FIELDS.difference(stock_data.columns)
    if missing:
        raise ValueError(
            "Stock data missing required fields: "
            + ", ".join(sorted(missing))
        )

    if "Universe Verification Status" not in verified_universe.columns:
        raise ValueError("NSE universe verification status is missing.")

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

    observation = pd.to_datetime(observation_date, errors="coerce")

    if pd.isna(observation):
        raise ValueError("A valid observation date is required.")

    observation = pd.Timestamp(observation).normalize()

    data = stock_data.copy()

    try:
        data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
        dates = data["Date"].dt.normalize()
    except (AttributeError, TypeError, ValueError):
        raise ValueError("Stock observations contain invalid dates.")

    if dates.isna().any():
        raise ValueError("Stock observations contain invalid dates.")

    if not dates.eq(observation).all():
        raise ValueError(
            "Every stock observation must match the requested date."
        )

    for column in (
        "Symbol",
        "Source",
        "Exchange",
        "Timeframe",
        "Fallback Reason",
        "Validation Status",
    ):
        data[column] = data[column].astype("string").str.strip()

        if data[column].isna().any():
            raise ValueError(
                f"Stock observations contain missing {column} values."
            )

    if data["Symbol"].eq("").any():
        raise ValueError("Stock observations contain blank symbols.")

    data["Symbol"] = data["Symbol"].str.upper()
    data["Source"] = data["Source"].str.upper()
    data["Exchange"] = data["Exchange"].str.upper()
    data["Timeframe"] = data["Timeframe"].str.lower()
    data["Validation Status"] = data["Validation Status"].str.upper()

    if not data["Source"].isin({"NSE", "YAHOO"}).all():
        raise ValueError("Unsupported stock data source.")

    if not data["Exchange"].eq("NSE").all():
        raise ValueError("Only NSE stock observations are supported.")

    if not data["Timeframe"].eq("1d").all():
        raise ValueError("Only daily stock observations are supported.")

    if not data["Validation Status"].eq("PASS").all():
        raise ValueError("Stock data validation did not PASS.")

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
    result["data_sources"] = sorted(data["Source"].unique().tolist())
    result["source_counts"] = data["Source"].value_counts().to_dict()
    result["yahoo_fallback_symbols"] = sorted(
        data.loc[yahoo_rows, "Symbol"].unique().tolist()
    )

    return result
    
