
"""NSE historical index downloader using current NSE API."""

from datetime import datetime
from pathlib import Path

import pandas as pd

from data.providers.nse_downloader import (
    NSE_BASE_URL,
    create_nse_session,
)

NSE_INDEX_URL = (
    f"{NSE_BASE_URL}/api/historicalOR/indicesHistory"
)

INDEX_ALIASES = {
    "NIFTY 50": "NIFTY 50",
    "NIFTY NEXT 50": "NIFTY NEXT 50",
    "NIFTY 100": "NIFTY 100",
    "NIFTY 200": "NIFTY 200",
    "NIFTY 500": "NIFTY 500",
    "NIFTY FMCG": "NIFTY FMCG",
}

INDEX_COLUMNS = {
    "Date": "EOD_TIMESTAMP",
    "Open": "EOD_OPEN_INDEX_VAL",
    "High": "EOD_HIGH_INDEX_VAL",
    "Low": "EOD_LOW_INDEX_VAL",
    "Close": "EOD_CLOSE_INDEX_VAL",
}


def download_index_history(index_name, start_date, end_date):
    """Download official NSE historical index OHLC."""

    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    if start > end:
        raise ValueError("Start date cannot be after end date.")

    index_name = index_name.strip().upper()

    if index_name not in INDEX_ALIASES:
        raise ValueError(
            f"Unsupported NSE index: {index_name}"
        )

    session = create_nse_session()

    params = {
        "indexType": INDEX_ALIASES[index_name],
        "from": start.strftime("%d-%m-%Y"),
        "to": end.strftime("%d-%m-%Y"),
    }

    response = session.get(
        NSE_INDEX_URL,
        params=params,
        headers={
            "Accept": "application/json, text/plain, */*",
            "Referer": (
                f"{NSE_BASE_URL}/reports-indices-historical-index-data"
            ),
        },
        timeout=60,
    )

    response.raise_for_status()

    try:
        payload = response.json()
    except ValueError as exc:
        content_type = response.headers.get(
            "content-type", "unknown"
        )
        preview = response.text[:160].replace("\n", " ")

        raise ValueError(
            "NSE index API returned non-JSON response. "
            f"Content-Type: {content_type}. "
            f"Response preview: {preview}"
        ) from exc

    if not isinstance(payload, dict):
        raise ValueError("Invalid NSE index response structure.")

    records = payload.get("data")

    if not isinstance(records, list) or not records:
        raise ValueError(
            f"No NSE index records returned for {index_name}."
        )

    raw = pd.DataFrame(records)

    required = set(INDEX_COLUMNS.values())
    missing = required.difference(raw.columns)

    if missing:
        raise ValueError(
            f"NSE index response missing fields: {sorted(missing)}"
        )

    output = pd.DataFrame({
        standard: raw[source]
        for standard, source in INDEX_COLUMNS.items()
    })

    output["Date"] = pd.to_datetime(
        output["Date"],
        errors="coerce",
        format="mixed",
        dayfirst=True,
    )

    if output["Date"].isna().any():
        raise ValueError("Invalid NSE index trading dates.")

    if output["Date"].duplicated().any():
        raise ValueError("Duplicate NSE index trading dates.")

    for column in ["Open", "High", "Low", "Close"]:
        output[column] = pd.to_numeric(
            output[column],
            errors="coerce",
        )

        if output[column].isna().any():
            raise ValueError(
                f"Invalid NSE index {column} values."
            )

        if (output[column] <= 0).any():
            raise ValueError(
                f"NSE index {column} must be positive."
            )

    if not output["Date"].between(
        pd.Timestamp(start),
        pd.Timestamp(end),
    ).all():
        raise ValueError(
            "NSE index response contains dates outside requested range."
        )

    invalid_high = output["High"] < output[
        ["Open", "Low", "Close"]
    ].max(axis=1)

    invalid_low = output["Low"] > output[
        ["Open", "High", "Close"]
    ].min(axis=1)

    if invalid_high.any() or invalid_low.any():
        raise ValueError("Invalid NSE index OHLC candles.")

    # Index traded volume is not assumed or fabricated.
    output["Volume"] = pd.NA

    output = output.sort_values("Date").reset_index(drop=True)

    output["Source"] = "NSE"
    output["Symbol"] = index_name

    return output


def save_nse_index_csv(df, index_name):
    """Save official NSE index data."""

    output_dir = Path("data/raw/nse")
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_name = index_name.upper().replace(" ", "_")

    output_file = output_dir / f"{safe_name}_nse.csv"

    df.to_csv(output_file, index=False)

    return str(output_file)
