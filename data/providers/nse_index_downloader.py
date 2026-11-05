
"""NSE historical index data downloader."""

from datetime import datetime
from pathlib import Path

import pandas as pd

from data.providers.nse_downloader import create_nse_session


NSE_INDEX_URL = (
    "https://www.nseindia.com/api/historical/indicesHistory"
)


# Accepted names and exact indexType values sent to NSE.
INDEX_ALIASES = {
    "NIFTY 50": "NIFTY 50",
    "NIFTY NEXT 50": "NIFTY NEXT 50",
    "NIFTY 100": "NIFTY 100",
    "NIFTY 200": "NIFTY 200",
    "NIFTY 500": "NIFTY 500",
    "NIFTY FMCG": "NIFTY FMCG",
}


COLUMN_ALIASES = {
    "Date": [
        "EOD_TIMESTAMP",
        "HistoricalDate",
        "TIMESTAMP",
        "Date",
    ],
    "Open": [
        "EOD_OPEN_INDEX_VAL",
        "OPEN_INDEX_VAL",
        "Open",
    ],
    "High": [
        "EOD_HIGH_INDEX_VAL",
        "HIGH_INDEX_VAL",
        "High",
    ],
    "Low": [
        "EOD_LOW_INDEX_VAL",
        "LOW_INDEX_VAL",
        "Low",
    ],
    "Close": [
        "EOD_CLOSE_INDEX_VAL",
        "CLOSE_INDEX_VAL",
        "Close",
    ],
    "Volume": [
        "EOD_VOLUME",
        "VOLUME",
        "Volume",
    ],
}


def _find_column(df, possible_names):
    for name in possible_names:
        if name in df.columns:
            return name

    return None


def _parse_index_dates(values):
    """Parse NSE index dates without shifting ISO calendar dates."""

    return pd.to_datetime(
        values,
        errors="coerce",
        format="mixed",
        dayfirst=True,
    )


def download_index_history(index_name, start_date, end_date):
    """
    Download historical NSE index data.

    Reject invalid and duplicate trading dates.
    Missing index Volume remains unavailable, not zero.
    """

    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    if start > end:
        raise ValueError("Start date cannot be after end date.")

    index_name = index_name.upper().strip()

    if index_name not in INDEX_ALIASES:
        raise ValueError(
            f"Unsupported index: {index_name}. "
            f"Supported: {list(INDEX_ALIASES)}"
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
        timeout=30,
    )

    response.raise_for_status()

    payload = response.json()
    records = payload.get("data", [])

    if not records:
        raise ValueError(
            f"No NSE index data returned for {index_name}. "
            "Check NSE access, index name, or date range."
        )

    df = pd.DataFrame(records)
    output = pd.DataFrame()

    for standard_name, aliases in COLUMN_ALIASES.items():
        source_column = _find_column(df, aliases)

        if source_column is not None:
            output[standard_name] = df[source_column]

        elif standard_name != "Volume":
            raise ValueError(
                f"NSE response missing required field: "
                f"{standard_name}. "
                f"Received columns: {list(df.columns)}"
            )

        else:
            output[standard_name] = pd.NA

    output["Date"] = _parse_index_dates(output["Date"])

    invalid_dates = int(output["Date"].isna().sum())

    if invalid_dates:
        raise ValueError(
            "NSE index response contains "
            f"{invalid_dates} invalid or missing trading dates."
        )

    duplicate_dates = int(output["Date"].duplicated().sum())

    if duplicate_dates:
        raise ValueError(
            "Duplicate dates found in NSE index data: "
            f"{duplicate_dates}. Data was not silently discarded."
        )

    for column in ["Open", "High", "Low", "Close", "Volume"]:
        output[column] = pd.to_numeric(
            output[column],
            errors="coerce",
        )

    output = output.sort_values("Date").reset_index(drop=True)

    output["Source"] = "NSE"
    output["Symbol"] = index_name

    return output


def save_nse_index_csv(df, index_name):
    """Save NSE index data as a raw CSV file."""

    output_dir = Path("data/raw/nse")
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_name = index_name.upper().replace(" ", "_")

    output_file = output_dir / f"{safe_name}_nse.csv"

    df.to_csv(output_file, index=False)

    return str(output_file)
