"""TradeLab Pro - Live AMFI and NSE Market Cap Verification."""

from pathlib import Path
import json
import sys
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from data.market_cap import (
    AMFI_PERIOD,
    AMFI_SOURCE_URL,
    fetch_amfi_market_cap,
    enrich_nse_universe_with_amfi,
)
from data.universe import load_nse_universe


REPORT_DIR = PROJECT_ROOT / "reports" / "market_cap"


def main():
    print("=" * 65)
    print("TRADELAB PRO - LIVE AMFI MARKET CAP AUDIT")
    print("=" * 65)

    print("AMFI source:", AMFI_SOURCE_URL)
    print("Expected period:", AMFI_PERIOD)

    # 1. Download official AMFI data.
    print("\n[1/5] Downloading official AMFI Excel...")

    amfi = fetch_amfi_market_cap()

    if amfi.empty:
        raise ValueError("AMFI returned no usable records.")

    required_amfi = {
        "ISIN",
        "AMFI NSE Symbol",
        "Market Cap Category",
    }

    missing = required_amfi - set(amfi.columns)

    if missing:
        raise ValueError(
            f"AMFI columns missing: {sorted(missing)}"
        )

    print("PASS: AMFI Excel downloaded and normalized.")
    print("AMFI records:", len(amfi))

    # 2. Validate category distribution.
    print("\n[2/5] Checking AMFI categories...")

    allowed = {
        "LARGE CAP",
        "MID CAP",
        "SMALL CAP",
    }

    categories = set(amfi["Market Cap Category"].dropna())

    if categories != allowed:
        raise ValueError(
            "Unexpected AMFI category distribution: "
            f"{sorted(categories)}"
        )

    category_counts = (
        amfi["Market Cap Category"]
        .value_counts()
        .to_dict()
    )

    for category in sorted(allowed):
        count = int(category_counts.get(category, 0))

        if count <= 0:
            raise ValueError(
                f"No AMFI records found for {category}."
            )

        print(f"{category}: {count}")

    # 3. Download verified NSE universe.
    print("\n[3/5] Downloading official NSE EQ universe...")

    nse = load_nse_universe()

    if nse.empty:
        raise ValueError("NSE universe is empty.")

    required_nse = {"Symbol", "ISIN", "Series"}
    missing = required_nse - set(nse.columns)

    if missing:
        raise ValueError(
            f"NSE universe columns missing: {sorted(missing)}"
        )

    print("PASS: NSE universe downloaded.")
    print("NSE universe records:", len(nse))

    # 4. Match using both ISIN and NSE Symbol.
    print("\n[4/5] Matching AMFI with NSE using ISIN + Symbol...")

    enriched = enrich_nse_universe_with_amfi(nse, amfi)

    status_counts = (
        enriched["Market Cap Match Status"]
        .value_counts()
        .to_dict()
    )

    matched = int(status_counts.get("MATCHED", 0))
    mismatched = int(
        status_counts.get("ISIN_SYMBOL_MISMATCH", 0)
    )
    unmatched = int(
        status_counts.get("NO_AMFI_MATCH", 0)
    )

    if matched <= 0:
        raise ValueError(
            "No NSE securities matched AMFI by both ISIN and Symbol."
        )

    print("Matched:", matched)
    print("ISIN/Symbol mismatch:", mismatched)
    print("No AMFI match:", unmatched)

    # 5. Validate eligible category counts.
    print("\n[5/5] Checking verified NSE category counts...")

    verified = enriched[
        enriched["Market Cap Match Status"].eq("MATCHED")
        & enriched["Series"].astype("string").str.upper().eq("EQ")
    ].copy()

    verified_counts = (
        verified["Market Cap Category"]
        .value_counts()
        .to_dict()
    )

    for category in sorted(allowed):
        count = int(verified_counts.get(category, 0))

        if count <= 0:
            raise ValueError(
                f"No verified NSE EQ securities for {category}."
            )

        print(f"Verified NSE {category}: {count}")

    # Save an audit report.
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    audit_time = datetime.now(timezone.utc)

    report = {
        "status": "PASS",
        "audit_time_utc": audit_time.isoformat(),
        "amfi_source": AMFI_SOURCE_URL,
        "amfi_period": AMFI_PERIOD,
        "amfi_records": int(len(amfi)),
        "nse_universe_records": int(len(nse)),
        "matched": matched,
        "isin_symbol_mismatch": mismatched,
        "no_amfi_match": unmatched,
        "amfi_category_counts": {
            key: int(value)
            for key, value in category_counts.items()
        },
        "verified_nse_category_counts": {
            key: int(value)
            for key, value in verified_counts.items()
        },
    }

    report_path = REPORT_DIR / "latest_live_audit.json"

    with open(report_path, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)

    print("\nAudit report:", report_path)
    print("\n" + "=" * 65)
    print("LIVE AMFI + NSE MARKET CAP AUDIT: PASS")
    print("=" * 65)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("\nLIVE AMFI AUDIT: FAIL")
        print(f"{type(error).__name__}: {error}")
        raise SystemExit(1)
