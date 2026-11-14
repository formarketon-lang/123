
"""Live NSE Primary and Yahoo Secondary verification.

Checks MARICO and all configured NSE benchmark/sector indexes.
Also forces one NSE failure to verify the real Yahoo fallback path.
"""

from datetime import date
from pathlib import Path
import sys

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import data.market_data_adapter as market_adapter
from data.market_data_adapter import (
    NSE_INDEX_SYMBOLS,
    fetch_market_history,
)

START_DATE = "2025-10-31"
END_DATE = date.today().isoformat()

EQUITY_SYMBOLS = ["MARICO"]

OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "nse"


def validate_result(df, name):
    """Validate downloaded OHLCV dates and price structure."""

    if not isinstance(df, pd.DataFrame) or df.empty:
        raise ValueError(f"{name}: empty or invalid dataset.")

    required = [
        "Date",
        "Open",
        "High",
        "Low",
        "Close",
        "Source",
        "Exchange",
        "Fetched At UTC",
        "Validation Status",
        "Fallback Reason",
    ]

    missing = [column for column in required if column not in df.columns]

    if missing:
        raise ValueError(f"{name}: missing columns: {missing}")

    result = df.copy()
    result["Date"] = pd.to_datetime(result["Date"], errors="coerce")

    if result["Date"].isna().any():
        raise ValueError(f"{name}: invalid trading dates found.")

    if result["Date"].duplicated().any():
        raise ValueError(f"{name}: duplicate trading dates found.")

    ordered_dates = result["Date"].sort_values()
    largest_gap_days = (
        ordered_dates.diff().dt.days.dropna().max()
    )
    if pd.notna(largest_gap_days) and largest_gap_days > 10:
        raise ValueError(
            f"{name}: historical coverage gap detected "
            f"({int(largest_gap_days)} calendar days)."
        )

    start = pd.Timestamp(START_DATE)
    end = pd.Timestamp(END_DATE)

    if not result["Date"].between(start, end).all():
        raise ValueError(f"{name}: dates outside requested range.")

    sources = result["Source"].astype(str).str.strip().str.upper()
    if sources.nunique(dropna=False) != 1:
        raise ValueError(f"{name}: mixed or missing data sources.")
    source = sources.iloc[0]
    if source not in {"NSE", "YAHOO"}:
        raise ValueError(f"{name}: unsupported source {source!r}.")

    exchanges = result["Exchange"].astype(str).str.strip().str.upper()
    if exchanges.nunique(dropna=False) != 1 or exchanges.iloc[0] != "NSE":
        raise ValueError(f"{name}: exchange provenance must be NSE.")

    statuses = (
        result["Validation Status"].astype(str).str.strip().str.upper()
    )
    if statuses.nunique(dropna=False) != 1 or statuses.iloc[0] != "PASS":
        raise ValueError(f"{name}: validation status is not PASS.")

    fetched_values = result["Fetched At UTC"].dropna().astype(str).str.strip()
    if fetched_values.empty or fetched_values.nunique() != 1:
        raise ValueError(f"{name}: missing or inconsistent fetch timestamp.")
    fetched_at = pd.to_datetime(
        fetched_values.iloc[0],
        errors="coerce",
        utc=True,
    )
    if pd.isna(fetched_at):
        raise ValueError(f"{name}: invalid Fetched At UTC timestamp.")

    fallback_reasons = (
        result["Fallback Reason"].fillna("").astype(str).str.strip()
    )
    if source == "YAHOO" and (
        fallback_reasons.empty or not fallback_reasons.iloc[0]
    ):
        raise ValueError(f"{name}: Yahoo fallback reason is missing.")

    for column in ["Open", "High", "Low", "Close"]:
        result[column] = pd.to_numeric(
            result[column],
            errors="coerce",
        )

        values = result[column].to_numpy(dtype=float)

        if not np.isfinite(values).all():
            raise ValueError(f"{name}: invalid {column} values.")

        if (result[column] <= 0).any():
            raise ValueError(f"{name}: non-positive {column} values.")

    invalid_high = result["High"] < result[
        ["Open", "Low", "Close"]
    ].max(axis=1)

    invalid_low = result["Low"] > result[
        ["Open", "High", "Close"]
    ].min(axis=1)

    if invalid_high.any() or invalid_low.any():
        raise ValueError(f"{name}: inconsistent OHLC candles.")

    return result.sort_values("Date").reset_index(drop=True)


def run_primary_check(name, symbol):
    """Check that the adapter actually returns NSE Primary data."""

    print(f"\n========== NSE PRIMARY: {name} ==========")
    print(f"Symbol: {symbol}")
    print(f"Range: {START_DATE} to {END_DATE}")

    try:
        df = fetch_market_history(
            symbol=symbol,
            start_date=START_DATE,
            end_date=END_DATE,
            interval="1d",
            exchange="NSE",
        )

        df = validate_result(df, name)

        source = str(df["Source"].iloc[0]).upper()

        if not (df["Source"].astype(str).str.upper() == source).all():
            raise ValueError("Mixed data sources found in one dataset.")

        if source != "NSE":
            reason = df["Fallback Reason"].iloc[0]
            raise ValueError(
                f"NSE Primary failed; adapter returned {source}. "
                f"Fallback reason: {reason}"
            )

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        safe_name = name.upper().replace(" ", "_")
        output_file = OUTPUT_DIR / f"{safe_name}_live_audit.csv"

        df.to_csv(output_file, index=False)

        print("STATUS: PASS")
        print("Actual source: NSE")
        print(f"Rows: {len(df)}")
        print(f"First date: {df['Date'].min().date()}")
        print(f"Last date: {df['Date'].max().date()}")
        print(f"Saved: {output_file}")

        return True

    except Exception as error:
        print("STATUS: FAIL")
        print(f"Reason: {type(error).__name__}: {error}")
        return False


def run_yahoo_fallback_check():
    """Force NSE failure and verify a real Yahoo response."""

    print("\n========== YAHOO SECONDARY FALLBACK ==========")

    original_downloader = market_adapter.download_index_history

    def forced_nse_failure(*args, **kwargs):
        raise RuntimeError("Intentional NSE failure for fallback test.")

    try:
        market_adapter.download_index_history = forced_nse_failure

        df = fetch_market_history(
            symbol="^NSEI",
            start_date=START_DATE,
            end_date=END_DATE,
            interval="1d",
            exchange="NSE",
        )

        df = validate_result(df, "YAHOO FALLBACK NIFTY 50")

        source = str(df["Source"].iloc[0]).upper()

        if source != "YAHOO":
            raise ValueError(
                f"Expected Yahoo fallback, received {source}."
            )

        reasons = df["Fallback Reason"].dropna().astype(str)

        if reasons.empty or not reasons.iloc[0].strip():
            raise ValueError("Yahoo fallback reason is missing.")

        output_dir = PROJECT_ROOT / "data" / "raw" / "yahoo"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / "NIFTY_50_forced_fallback.csv"
        df.to_csv(output_file, index=False)

        print("STATUS: PASS")
        print("Actual source: Yahoo")
        print(f"Rows: {len(df)}")
        print(f"Fallback reason: {reasons.iloc[0]}")
        print(f"Saved: {output_file}")

        return True

    except Exception as error:
        print("STATUS: FAIL")
        print(f"Reason: {type(error).__name__}: {error}")
        return False

    finally:
        market_adapter.download_index_history = original_downloader


def main():
    results = {}

    print("TRADELAB PRO - NSE LIVE INDEX AUDIT")
    print(f"Date range: {START_DATE} to {END_DATE}")

    # Equity Primary check.
    for symbol in EQUITY_SYMBOLS:
        results[symbol] = run_primary_check(symbol, symbol)

    # All configured NSE index mappings.
    for yahoo_symbol, nse_index_name in NSE_INDEX_SYMBOLS.items():
        results[nse_index_name] = run_primary_check(
            nse_index_name,
            yahoo_symbol,
        )

    # Real Yahoo fallback test.
    fallback_passed = run_yahoo_fallback_check()

    print("\n========== FINAL LIVE AUDIT ==========")

    for name, passed in results.items():
        print(f"{name}: {'PASS' if passed else 'FAIL'}")

    print(
        "YAHOO FORCED FALLBACK: "
        f"{'PASS' if fallback_passed else 'FAIL'}"
    )

    primary_passed = sum(results.values())
    primary_total = len(results)

    print(f"\nNSE Primary: {primary_passed}/{primary_total}")
    print(f"Yahoo Fallback: {'PASS' if fallback_passed else 'FAIL'}")

    if primary_passed != primary_total or not fallback_passed:
        print("\nNSE LIVE AUDIT: INCOMPLETE")
        raise SystemExit(1)

    print("\nNSE LIVE AUDIT: ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
