
"""NSE historical equity downloader using current NSE historical API."""

import csv
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pandas as pd
from curl_cffi import requests

NSE_BASE_URL = "https://www.nseindia.com"
NSE_BOOTSTRAP_URL = f"{NSE_BASE_URL}/report-detail/eq_security"
NSE_EQUITY_HISTORY_URL = (
    f"{NSE_BASE_URL}/api/historicalOR/"
    "generateSecurityWiseHistoricalData"
)

HTML_ACCEPT = (
    "text/html,application/xhtml+xml,"
    "application/xml;q=0.9,*/*;q=0.8"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": NSE_BOOTSTRAP_URL,
    "X-Requested-With": "XMLHttpRequest",
}


def create_nse_session():
    """Initialize an NSE session using the historical reports page."""
    session = requests.Session(impersonate="chrome")
    session.headers.update(HEADERS)

    response = session.get(
        NSE_BOOTSTRAP_URL,
        headers={
            "Accept": HTML_ACCEPT,
            "Referer": f"{NSE_BASE_URL}/",
        },
        timeout=30,
    )
    response.raise_for_status()
    session.headers.update(HEADERS)
    return session


def _to_numeric_clean(series, column):
    """Convert NSE numeric strings safely without weakening validation."""
    cleaned = (
        series.astype("string")
        .str.replace(",", "", regex=False)
        .str.replace("\u00a0", "", regex=False)
        .str.replace(" ", "", regex=False)
        .str.strip()
        .replace("", pd.NA)
    )

    converted = pd.to_numeric(cleaned, errors="coerce")

    invalid = converted.isna()
    if invalid.any():
        samples = series.loc[invalid].astype(str).head(5).tolist()
        raise ValueError(
            f"Missing or invalid NSE {column} values. "
            f"Invalid samples: {samples}"
        )

    return converted


def _read_nse_equity_csv(content):
    """Read NSE CSV and safely repair unquoted volume thousands separators."""
    try:
        rows = list(csv.reader(StringIO(content)))
    except csv.Error as exc:
        raise ValueError(
            f"Unable to parse NSE equity CSV: {exc}"
        ) from exc

    if not rows:
        raise ValueError("NSE returned an empty equity CSV.")

    headers = [str(column).strip() for column in rows[0]]

    if not headers:
        raise ValueError("NSE equity CSV has no header.")

    volume_aliases = {
        "Total Traded Quantity",
        "Volume",
        "CH_TOT_TRADED_QTY",
    }

    volume_index = next(
        (
            index
            for index, name in enumerate(headers)
            if name in volume_aliases
        ),
        None,
    )

    normalized_rows = []

    for row_number, row in enumerate(rows[1:], start=2):
        if not row or all(not str(value).strip() for value in row):
            continue

        if len(row) > len(headers):
            can_repair_volume = (
                volume_index == len(headers) - 1
                and len(row[volume_index:]) >= 2
                and all(
                    part.strip().isdigit()
                    for part in row[volume_index:]
                )
            )

            if not can_repair_volume:
                raise ValueError(
                    "Malformed NSE equity CSV row "
                    f"{row_number}: unexpected extra columns."
                )

            row = row[:volume_index] + [
                ",".join(row[volume_index:])
            ]

        if len(row) != len(headers):
            raise ValueError(
                "Malformed NSE equity CSV row "
                f"{row_number}: expected {len(headers)} columns, "
                f"received {len(row)}."
            )

        normalized_rows.append(row)

    return pd.DataFrame(normalized_rows, columns=headers)


def _parse_equity_csv(response, symbol):
    """Parse and validate NSE's official historical CSV."""
    content_type = response.headers.get("content-type", "").lower()
    content = response.text

    if not content or not content.strip():
        raise ValueError("NSE returned an empty equity response.")

    if (
        "text/html" in content_type
        or content.lstrip().lower().startswith(
            ("<!doctype html", "<html")
        )
    ):
        raise ValueError(
            "NSE returned HTML instead of equity CSV. "
            "Session or access was rejected."
        )

    raw = _read_nse_equity_csv(content)
    raw.columns = [str(column).strip() for column in raw.columns]

    aliases = {
        "Date": ["Date", "CH_TIMESTAMP"],
        "Open": ["Open Price", "Open", "CH_OPENING_PRICE"],
        "High": ["High Price", "High", "CH_TRADE_HIGH_PRICE"],
        "Low": ["Low Price", "Low", "CH_TRADE_LOW_PRICE"],
        "Close": [
            "Close Price", "Close", "CH_CLOSING_PRICE"
        ],
        "Volume": [
            "Total Traded Quantity",
            "Volume",
            "CH_TOT_TRADED_QTY",
        ],
    }

    selected = {}
    for standard, candidates in aliases.items():
        found = next(
            (name for name in candidates if name in raw.columns),
            None,
        )
        if found is None:
            raise ValueError(
                f"NSE equity CSV missing {standard}. "
                f"Received columns: {list(raw.columns)}"
            )
        selected[standard] = raw[found]

    result = pd.DataFrame(selected)

    if "Series" in raw.columns:
        equity_mask = (
            raw["Series"].astype(str).str.strip().str.upper() == "EQ"
        )
        result = result.loc[equity_mask].copy()

    if "Symbol" in raw.columns:
        symbol_mask = (
            raw.loc[result.index, "Symbol"]
            .astype(str)
            .str.strip()
            .str.upper()
            == symbol.upper()
        )
        result = result.loc[symbol_mask].copy()

    if result.empty:
        raise ValueError(
            f"No EQ-series NSE records found for {symbol}."
        )

    result["Date"] = pd.to_datetime(
        result["Date"],
        errors="coerce",
        format="mixed",
        dayfirst=True,
    )

    if result["Date"].isna().any():
        raise ValueError("Invalid dates in NSE equity response.")

    if result["Date"].duplicated().any():
        raise ValueError("Duplicate dates in NSE equity response.")

    for column in ["Open", "High", "Low", "Close", "Volume"]:
        result[column] = _to_numeric_clean(result[column], column)

    for column in ["Open", "High", "Low", "Close"]:
        if (result[column] <= 0).any():
            raise ValueError(
                f"NSE equity {column} values must be positive."
            )

    if (result["Volume"] < 0).any():
        raise ValueError("Negative NSE equity volume detected.")

    invalid_high = result["High"] < result[
        ["Open", "Low", "Close"]
    ].max(axis=1)

    invalid_low = result["Low"] > result[
        ["Open", "High", "Close"]
    ].min(axis=1)

    if invalid_high.any() or invalid_low.any():
        raise ValueError("Invalid NSE equity OHLC candles.")

    return result.sort_values("Date").reset_index(drop=True)


def download_equity_history(symbol, start_date, end_date):
    """Download NSE official historical equity OHLCV."""
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("A valid NSE equity symbol is required.")

    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    if start > end:
        raise ValueError("Start date cannot be after end date.")

    symbol = symbol.strip().upper()
    session = create_nse_session()

    params = {
        "symbol": symbol,
        "from": start.strftime("%d-%m-%Y"),
        "to": end.strftime("%d-%m-%Y"),
        "type": "priceVolumeDeliverable",
        "series": "ALL",
        "csv": "true",
    }

    response = session.get(
        NSE_EQUITY_HISTORY_URL,
        params=params,
        headers={
            "Accept": "text/csv,application/csv,*/*",
            "Referer": NSE_BOOTSTRAP_URL,
        },
        timeout=60,
    )
    fetched_at_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    response.raise_for_status()

    result = _parse_equity_csv(response, symbol)

    if not result["Date"].between(
        pd.Timestamp(start), pd.Timestamp(end)
    ).all():
        raise ValueError(
            "NSE equity response contains dates outside requested range."
        )

    result.attrs["fetched_at_utc"] = fetched_at_utc
    return result


def save_nse_csv(df, symbol):
    """Save NSE raw equity data."""
    output_dir = Path("data/raw/nse")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"{symbol.upper()}_nse.csv"
    df.to_csv(output_file, index=False)
    return str(output_file)
