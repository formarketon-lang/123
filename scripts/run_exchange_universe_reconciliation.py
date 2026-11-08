"""Run independent NSE and BSE universe reconciliation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

from data.providers.exchange_universe_reconciliation import (
    build_exchange_universe_reconciliation,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "exchange_universe"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def metadata(exchange, path, source_url, trading_date):
    return {
        "exchange": exchange,
        "source_url": source_url,
        "filename": path.name,
        "downloaded_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "trading_date": trading_date,
        "sha256": sha256_file(path),
    }


def main():
    parser = argparse.ArgumentParser()

    for name in ["nse", "bse"]:
        parser.add_argument(
            f"--{name}-input", type=Path, required=True
        )
        parser.add_argument(
            f"--{name}-source-url", required=True
        )
        parser.add_argument(
            f"--{name}-trading-date", required=True
        )

    parser.add_argument(
        "--output-dir", type=Path, default=OUTPUT
    )

    args = parser.parse_args()

    for path in [args.nse_input, args.bse_input]:
        if not path.is_file() or path.suffix.lower() != ".csv":
            parser.error(f"Invalid CSV snapshot: {path}")

    nse = pd.read_csv(
        args.nse_input, dtype="string", low_memory=False
    )
    bse = pd.read_csv(
        args.bse_input, dtype="string", low_memory=False
    )

    nse_meta = metadata(
        "NSE", args.nse_input,
        args.nse_source_url, args.nse_trading_date,
    )
    bse_meta = metadata(
        "BSE", args.bse_input,
        args.bse_source_url, args.bse_trading_date,
    )

    detail, summary = build_exchange_universe_reconciliation(
        nse, bse, nse_meta, bse_meta
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)

    detail.to_csv(
        args.output_dir / "exchange_universe_detail.csv",
        index=False,
    )

    (args.output_dir / "exchange_universe_summary.json").write_text(
        json.dumps(
            {
                "summary": summary,
                "nse_metadata": nse_meta,
                "bse_metadata": bse_meta,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2))

    if summary["status"] != "PASS":
        raise SystemExit(
            "REVIEW: exchange universe reconciliation failed."
        )

    print("Exchange universe identity reconciliation: PASS")
    print("Sector Mapping remains OFF.")


if __name__ == "__main__":
    main()