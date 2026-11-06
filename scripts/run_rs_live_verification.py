"""TradeLab Pro - Live Multi-Benchmark RS Verification.

Runs the real Relative Strength scanner against live market data.
Verifies MARICO against Nifty 50, Nifty 100 and Nifty 500.
Creates CSV and JSON audit reports for GitHub Actions.
"""

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import json
import math
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.rs_scanner import execute_scanner
from data.benchmark_mapping import MAIN_BENCHMARKS
from data.universe import load_nse_universe


STOCK_SYMBOL = "MARICO"

BENCHMARKS = [
    "Nifty 50",
    "Nifty 100",
    "Nifty 500",
]

WINDOWS = [
    "1M",
    "3M",
    "6M",
    "1Y",
]

OUTPUT_DIR = (
    PROJECT_ROOT
    / "reports"
    / "phase3_live_verification"
)


def validate_universe(universe):
    """Verify MARICO exists in the official NSE EQ universe."""

    if universe is None or universe.empty:
        raise ValueError("Official NSE universe is empty.")

    required = {"Symbol", "ISIN", "Series"}
    missing = required.difference(universe.columns)

    if missing:
        raise ValueError(
            "NSE universe missing columns: "
            + ", ".join(sorted(missing))
        )

    eligible = universe[
        (
            universe["Series"]
            .astype("string")
            .str.strip()
            .str.upper()
            == "EQ"
        )
        & universe["ISIN"].notna()
    ]

    symbols = set(
        eligible["Symbol"]
        .dropna()
        .astype("string")
        .str.strip()
        .str.upper()
    )

    if STOCK_SYMBOL not in symbols:
        raise ValueError(
            "MARICO was not found in verified NSE EQ universe."
        )

    print("NSE UNIVERSE: PASS")
    print(f"Verified eligible EQ securities: {len(symbols)}")
    print(f"Verified test stock: {STOCK_SYMBOL}")

    return universe


def validate_results(result):
    """Validate independent benchmark results and calculations."""

    if result.get("benchmark_errors"):
        raise ValueError(
            "Benchmark download errors: "
            + json.dumps(
                result["benchmark_errors"],
                ensure_ascii=False,
            )
        )

    rows = result.get("main_results", [])

    if not rows:
        raise ValueError("Scanner returned no Main Benchmark results.")

    frame = pd.DataFrame(rows)

    required = [
        "Benchmark",
        "Stock",
        "Window",
        "Stock Return (%)",
        "Main Index Return (%)",
        "Excess Return (%)",
        "Common Sessions",
        "Stock Source",
        "Main Index Source",
    ]

    missing = [
        column for column in required
        if column not in frame.columns
    ]

    if missing:
        raise ValueError(
            "Scanner result missing columns: "
            + ", ".join(missing)
        )

    expected_windows = ["Selected Period"] + [
        f"{window}" for window in WINDOWS
    ]

    expected_pairs = {
        (benchmark, window)
        for benchmark in BENCHMARKS
        for window in expected_windows
    }

    actual_pairs = set(
        zip(frame["Benchmark"], frame["Window"])
    )

    missing_pairs = sorted(expected_pairs - actual_pairs)

    if missing_pairs:
        raise ValueError(
            "Missing benchmark/window results: "
            + json.dumps(missing_pairs)
        )

    if set(frame["Benchmark"]) != set(BENCHMARKS):
        raise ValueError(
            "Returned benchmark list does not match selection."
        )

    if set(frame["Stock"]) != {STOCK_SYMBOL}:
        raise ValueError(
            "Unexpected stock symbols found in live results."
        )

    for column in [
        "Stock Return (%)",
        "Main Index Return (%)",
        "Excess Return (%)",
    ]:
        frame[column] = pd.to_numeric(
            frame[column],
            errors="coerce",
        )

        if not frame[column].map(
            lambda value: math.isfinite(value)
        ).all():
            raise ValueError(
                f"Invalid numeric values in {column}."
            )

    if (frame["Common Sessions"] < 2).any():
        raise ValueError(
            "At least one comparison has fewer than two common sessions."
        )

    # Verify Excess Return = Stock Return - Main Index Return.
    calculated = (
        frame["Stock Return (%)"]
        - frame["Main Index Return (%)"]
    )

    difference = (
        calculated - frame["Excess Return (%)"]
    ).abs()

    if (difference > 0.02).any():
        raise ValueError(
            "Excess Return calculation verification failed."
        )

    # Only actual provider metadata is accepted.
    allowed_sources = {"NSE", "YAHOO"}

    for column in ["Stock Source", "Main Index Source"]:
        normalized = (
            frame[column]
            .astype(str)
            .str.strip()
            .str.upper()
        )

        invalid = sorted(
            set(normalized) - allowed_sources
        )

        if invalid:
            raise ValueError(
                f"Unexpected source in {column}: {invalid}"
            )

    print("\nBENCHMARK RESULT VALIDATION: PASS")

    for benchmark in BENCHMARKS:
        view = frame[
            frame["Benchmark"] == benchmark
        ]

        print(
            f"{benchmark}: PASS | "
            f"{len(view)} windows | "
            f"Source: "
            f"{', '.join(sorted(set(view['Main Index Source'])))}"
        )

    print("EXCESS RETURN CALCULATION: PASS")
    print("COMMON SESSION VALIDATION: PASS")
    print("DATA SOURCE VALIDATION: PASS")

    return frame


def main():
    print("=" * 60)
    print("TRADELAB PRO - PHASE 3 LIVE RS VERIFICATION")
    print("=" * 60)

    print(f"Test Stock: {STOCK_SYMBOL}")
    print(f"Benchmarks: {', '.join(BENCHMARKS)}")

    for benchmark in BENCHMARKS:
        if benchmark not in MAIN_BENCHMARKS:
            raise ValueError(
                f"Benchmark mapping missing: {benchmark}"
            )

        print(
            f"Mapping verified: "
            f"{benchmark} -> {MAIN_BENCHMARKS[benchmark]}"
        )

    end_date = date.today()
    start_date = end_date - timedelta(days=400)

    print(f"\nStart Date: {start_date}")
    print(f"End Date: {end_date}")

    print("\nSTEP 1: Loading official NSE universe...")

    universe = validate_universe(
        load_nse_universe()
    )

    print("\nSTEP 2: Running actual RS scanner...")

    result = execute_scanner(
        sector=None,
        manual_symbols="",
        exchange="NSE",
        benchmark_name=BENCHMARKS[0],
        benchmark_names=BENCHMARKS,
        sector_benchmark_symbol=None,
        start_date=start_date,
        end_date=end_date,
        custom_windows=WINDOWS,
        selected_symbols=[STOCK_SYMBOL],
        universe=universe,
        market_cap_filter="All Market Caps",
        market_cap_universe=None,
    )

    print("\nSTEP 3: Validating live scanner results...")

    frame = validate_results(result)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    csv_path = OUTPUT_DIR / "marico_multi_benchmark_rs.csv"
    json_path = OUTPUT_DIR / "marico_multi_benchmark_rs.json"

    frame.to_csv(
        csv_path,
        index=False,
        encoding="utf-8-sig",
    )

    report = {
        "project": "TradeLab Pro",
        "verification": "Phase 3 Multi-Benchmark Live RS",
        "status": "PASS",
        "generated_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "stock": STOCK_SYMBOL,
        "exchange": "NSE",
        "start_date": str(start_date),
        "end_date": str(end_date),
        "benchmarks": BENCHMARKS,
        "windows": result.get("windows", []),
        "result_count": len(frame),
        "benchmark_sources": result.get(
            "benchmark_sources",
            {},
        ),
        "results": frame.to_dict("records"),
        "errors": result.get("errors", []),
    }

    with json_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            report,
            file,
            indent=2,
            ensure_ascii=False,
            default=str,
        )

    print("\nSTEP 4: Reports generated.")

    print(f"CSV: {csv_path}")
    print(f"JSON: {json_path}")
    print(f"Total result rows: {len(frame)}")

    print("\nPHASE 3 LIVE RS VERIFICATION: ALL CHECKS PASSED")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("\nPHASE 3 LIVE RS VERIFICATION: FAILED")
        print(f"{type(error).__name__}: {error}")
        raise SystemExit(1)
          
