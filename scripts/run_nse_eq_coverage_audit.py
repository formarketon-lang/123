"""Run the full NSE EQ classification identity coverage audit.

Inputs are explicit CSV snapshots.
This script does not download data or activate sector mapping.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from data.providers.nse_eq_coverage_audit import (
    build_nse_eq_coverage_audit,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT / "reports" / "industry_classification"
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compare an NSE EQ universe CSV with a company "
            "classification CSV using exact Symbol and ISIN."
        )
    )

    parser.add_argument(
        "--classification-input",
        type=Path,
        required=True,
        help="Company-level classification CSV.",
    )
    parser.add_argument(
        "--nse-universe-input",
        type=Path,
        required=True,
        help="Saved NSE MII security-master CSV.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for audit reports.",
    )

    args = parser.parse_args()

    for label, path in [
        ("Classification", args.classification_input),
        ("NSE universe", args.nse_universe_input),
    ]:
        if not path.exists() or not path.is_file():
            parser.error(f"{label} CSV not found: {path}")

        if path.suffix.lower() != ".csv":
            parser.error(f"{label} input must be a CSV file.")

    classification = pd.read_csv(
        args.classification_input,
        dtype="string",
        encoding="utf-8-sig",
        low_memory=False,
    )

    nse_universe = pd.read_csv(
        args.nse_universe_input,
        dtype="string",
        encoding="utf-8-sig",
        low_memory=False,
    )

    detail, classification_only, summary = (
        build_nse_eq_coverage_audit(
            classification=classification,
            nse_universe=nse_universe,
        )
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)

    detail_path = (
        args.output_dir / "nse_eq_coverage_detail.csv"
    )
    classification_only_path = (
        args.output_dir / "classification_symbols_not_in_nse_eq.csv"
    )
    summary_path = (
        args.output_dir / "nse_eq_coverage_summary.json"
    )

    detail.to_csv(detail_path, index=False)
    classification_only.to_csv(
        classification_only_path,
        index=False,
    )

    summary["classification_input_file"] = (
        args.classification_input.name
    )
    summary["nse_universe_input_file"] = (
        args.nse_universe_input.name
    )

    summary_path.write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("\n========== NSE EQ COVERAGE AUDIT ==========")

    for key, value in summary.items():
        print(f"{key}: {value}")

    print("\n========== OUTPUT FILES ==========")
    print(f"Detail: {detail_path}")
    print(f"Classification-only: {classification_only_path}")
    print(f"Summary: {summary_path}")

    if not summary["full_universe_coverage_passed"]:
        raise SystemExit(
            "COVERAGE REVIEW: full NSE EQ identity coverage "
            "has not passed. Sector mapping remains disabled."
        )

    print("\nCOVERAGE PASS: all NSE EQ identity rows matched.")
    print("Sector Mapping remains disabled.")


if __name__ == "__main__":
    main()
                                                   
