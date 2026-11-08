"""Run real NSE/BSE cash-equity reconciliation from supplied snapshots."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from data.providers.exchange_universe_reconciliation import (
    build_exchange_universe_reconciliation,
    load_bse_equity_universe,
    load_nse_cm_diagnostic,
    load_nse_equity_universe,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "exchange_universe"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024), b""
        ):
            digest.update(chunk)

    return digest.hexdigest()


def make_metadata(
    exchange: str,
    path: Path,
    source_url: str | None,
    trading_date: str,
    downloaded_at_utc: str | None,
) -> dict:
    return {
        "exchange": exchange,
        "source_url": source_url or "",
        "filename": path.name,
        "downloaded_at_utc": downloaded_at_utc or "",
        "trading_date": trading_date,
        "sha256": sha256_file(path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--nse-input",
        type=Path,
        required=True,
        help="NSE EQUITY_L.csv (primary listed universe)",
    )
    parser.add_argument(
        "--bse-input",
        type=Path,
        required=True,
        help="BSE scrip ZIP containing BSE_EQ_SCRIP*.csv",
    )
    parser.add_argument(
        "--nse-cm-diagnostic",
        type=Path,
        action="append",
        default=[],
        help=(
            "Optional NSE CM security .csv.gz; "
            "repeat for each variant (diagnostic only)"
        ),
    )
    parser.add_argument("--nse-source-url")
    parser.add_argument("--bse-source-url")
    parser.add_argument("--nse-downloaded-at-utc")
    parser.add_argument("--bse-downloaded-at-utc")
    parser.add_argument("--nse-trading-date", required=True)
    parser.add_argument("--bse-trading-date", required=True)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)

    args = parser.parse_args()

    for path in [args.nse_input, args.bse_input]:
        if not path.is_file():
            parser.error(f"Input file does not exist: {path}")

    for diagnostic_path in args.nse_cm_diagnostic:
        if not diagnostic_path.is_file():
            parser.error(
                f"NSE CM diagnostic does not exist: {diagnostic_path}"
            )

    nse, nse_load = load_nse_equity_universe(args.nse_input)
    bse, bse_load = load_bse_equity_universe(args.bse_input)

    nse_meta = make_metadata(
        "NSE",
        args.nse_input,
        args.nse_source_url,
        args.nse_trading_date,
        args.nse_downloaded_at_utc,
    )
    bse_meta = make_metadata(
        "BSE",
        args.bse_input,
        args.bse_source_url,
        args.bse_trading_date,
        args.bse_downloaded_at_utc,
    )

    detail, summary = build_exchange_universe_reconciliation(
        nse, bse, nse_meta, bse_meta
    )

    diagnostics = {
        "nse_equity_list": nse_load,
        "bse_security_master": bse_load,
    }

    if args.nse_cm_diagnostic:
        diagnostics["nse_cm_diagnostics"] = []

        for diagnostic_path in args.nse_cm_diagnostic:
            _, cm_diag = load_nse_cm_diagnostic(diagnostic_path)
            cm_diag["filename"] = diagnostic_path.name
            diagnostics["nse_cm_diagnostics"].append(cm_diag)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    detail.to_csv(
        args.output_dir / "exchange_universe_detail.csv",
        index=False,
    )

    payload = {
        "summary": summary,
        "diagnostics": diagnostics,
        "nse_metadata": nse_meta,
        "bse_metadata": bse_meta,
        "limitations": [
            (
                "Source URLs and original download timestamps must be "
                "supplied to pass provenance validation."
            ),
            (
                "NSE CM security files are diagnostics only; "
                "NSE EQUITY_L.csv EQ series is the primary listed universe."
            ),
            (
                "Sector mapping is not inferred or activated by this audit."
            ),
        ],
    }

    (
        args.output_dir / "exchange_universe_summary.json"
    ).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps(payload, indent=2, ensure_ascii=False))

    if summary["status"] != "PASS":
        raise SystemExit(
            "REVIEW: exchange universe identity/provenance checks "
            "require resolution."
        )

    print("Exchange universe identity reconciliation: PASS")
    print("Sector Mapping remains OFF.")


if __name__ == "__main__":
    main()