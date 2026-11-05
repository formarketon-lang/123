
"""NSE historical equity downloader using current NSE historical API."""

from datetime import datetime
from io import StringIO
from pathlib import Path

import pandas as pd
from curl_cffi import requests

NSE_BASE_URL = "https://www.nseindia.com"

NSE_BOOTSTRAP_URL = (
    f"{NSE_BASE_URL}/report-detail/eq_security"
)

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

    try:
        raw = pd.read_csv(StringIO(content))
    except Exception as exc:
        raise ValueError(
            f"Unable to parse NSE equity CSV: {exc}"
        ) from exc

    raw.columns = [
        str(column).strip()
        for column in raw.columns
    ]

    aliases = {
        "Date": ["Date", "CH_TIMESTAMP"],
        "Open": ["Open Price", "Open", "CH_OPENING_PRICE"],
        "High": ["High Price", "High", "CH_TRADE_HIGH_PRICE"],
        "Low": ["Low Price", "Low", "CH_TRADE_LOW_PRICE"],
        "Close": [
            "Close Price",
            "Close",
            "CH_CLOSING_PRICE",
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

    # The ALL series response can contain non-EQ series.
    if "Series" in raw.columns:
        equity_mask = (
            raw["Series"].astype(str).str.strip().str.upper()
            == "EQ"
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
        result[column] = pd.to_numeric(
            result[column],
            errors="coerce",
        )

        if result[column].isna().any():
            raise ValueError(
                f"Missing or invalid NSE {column} values."
            )

    if (result["Volume"] < 0).any():
        raise ValueError("Negative NSE equity volume detected.")

    result = result.sort_values("Date").reset_index(drop=True)

    return result


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

    response.raise_for_status()

    result = _parse_equity_csv(response, symbol)

    if not result["Date"].between(
        pd.Timestamp(start),
        pd.Timestamp(end),
    ).all():
        raise ValueError(
            "NSE equity response contains dates outside requested range."
        )

    return result


def save_nse_csv(df, symbol):
    """Save NSE raw equity data."""

    output_dir = Path("data/raw/nse")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"{symbol.upper()}_nse.csv"

    df.to_csv(output_file, index=False)

    return str(output_file)
