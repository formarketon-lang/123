"""Application service integrating validated stock data with Breadth Core."""

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
    """Analyze breadth only with validated data and a dated NSE MII universe."""

    if not isinstance(stock_data, pd.DataFrame) or stock_data.empty:
        raise ValueError("Stock observations are empty or invalid.")

    if not isinstance(verified_universe, pd.DataFrame):
        raise TypeError("A verified NSE universe DataFrame is required.")

    missing = REQUIRED_STOCK_FIELDS.difference(stock_data.columns)
    if missing:
        raise ValueError(
            "Stock data missing provenance fields: "
            + ", ".join(sorted(missing))
        )

    if verified_universe.empty:
        raise ValueError("Verified NSE universe is empty.")

    if "Universe Verification Status" not in verified_universe.columns:
        raise ValueError("NSE universe verification status is missing.")

    statuses = (
        verified_universe["Universe Verification Status"]
        .dropna()
        .astype(str)
        .str.upper()
        .unique()
    )

    if len(statuses) != 1 or statuses[0] != "MII_DATED":
        raise ValueError(
            "Breadth requires a dated official NSE MII universe."
        )

    data = stock_data.copy()

    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    if data["Date"].isna().any():
        raise ValueError("Stock observations contain invalid dates.")

    observation = pd.to_datetime(observation_date, errors="coerce")
    if pd.isna(observation):
        raise ValueError("A valid observation date is required.")

    observation = pd.Timestamp(observation).normalize()

    if not data["Date"].dt.normalize().eq(observation).all():
        raise ValueError(
            "Every stock observation must match the requested date."
        )

    for column in (
        "Source",
        "Exchange",
        "Timeframe",
        "Validation Status",
        "Fallback Reason",
    ):
        data[column] = data[column].astype("string").str.strip()

        if data[column].isna().any() or data[column].eq("").any():
            raise ValueError(
                f"Missing stock provenance in {column}."
            )

    data["Source"] = data["Source"].str.upper()
    data["Exchange"] = data["Exchange"].str.upper()
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
            "Yahoo stock observations require a fallback reason."
        )

    result = analyze_market_breadth(
        stock_data=data[
            ["Symbol", "Previous Close", "Current Close"]
        ],
        verified_universe=verified_universe,
        observation_date=observation,
    )

    result["analysis_status"] = result["coverage_status"]
    result["observation_date"] = observation.date().isoformat()
    result["data_sources"] = sorted(data["Source"].unique().tolist())
    result["source_counts"] = (
        data["Source"].value_counts().to_dict()
    )
    result["yahoo_fallback_symbols"] = sorted(
        data.loc[yahoo_rows, "Symbol"]
        .astype(str)
        .str.strip()
        .str.upper()
        .tolist()
    )

    return result
