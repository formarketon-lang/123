"""Run NSE/BSE reconciliation using retained downloader provenance."""
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
    validate_metadata,
    verify_snapshot_file,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "exchange_universe"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_snapshot_provenance(
    snapshot: Path,
    provenance_path: Path | None,
    exchange: str,
    trading_date: str,
) -> tuple[dict, dict]:
    """Load and verify downloader metadata against retained bytes."""
    if provenance_path is None:
        return {}, {
            "status": "REVIEW",
            "reason": "Provenance JSON was not supplied.",
            "independent_external_checksum": False,
        }

    try:
        raw = json.loads(
            provenance_path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        return {}, {
            "status": "REVIEW",
            "reason": f"Cannot read provenance JSON: {exc}",
            "independent_external_checksum": False,
        }

    required = {
        "exchange",
        "source_url",
        "final_source_url",
        "redirect_chain",
        "filename",
        "downloaded_at_utc",
        "sha256",
        "size_bytes",
        "original_bytes_retained",
        "redirects_validated",
    }

    missing = sorted(required.difference(raw))
    if missing:
        return {}, {
            "status": "REVIEW",
            "reason": "Missing provenance fields: " + ", ".join(missing),
            "independent_external_checksum": False,
        }

    if not snapshot.is_file():
        return {}, {
            "status": "REVIEW",
            "reason": "Snapshot file does not exist.",
            "independent_external_checksum": False,
        }

    if str(raw["exchange"]).upper() != exchange:
        reason = "Provenance exchange does not match input."
    elif raw["filename"] != snapshot.name:
        reason = "Provenance filename does not match snapshot."
    elif raw["original_bytes_retained"] is not True:
        reason = "Original downloaded bytes were not confirmed."
    elif raw["redirects_validated"] is not True:
        reason = "Redirect validation was not confirmed."
    elif not isinstance(raw["redirect_chain"], list):
        reason = "Redirect chain must be a list."
    elif raw["size_bytes"] != snapshot.stat().st_size:
        reason = "Snapshot size does not match provenance."
    elif sha256_file(snapshot).lower() != str(raw["sha256"]).lower():
        reason = "Snapshot SHA-256 does not match provenance."
    else:
        reason = ""

    candidates = [
        raw.get("source_url"),
        *raw.get("redirect_chain", []),
        raw.get("final_source_url"),
    ]

    if not reason:
        for url in candidates:
            check = {
                "exchange": exchange,
                "source_url": url,
                "filename": snapshot.name,
                "downloaded_at_utc": raw["downloaded_at_utc"],
                "trading_date": trading_date,
                "sha256": raw["sha256"],
            }
            if not validate_metadata(check, exchange):
                reason = "Unapproved or invalid source URL in provenance."
                break

    if reason:
        return {}, {
            "status": "REVIEW",
            "reason": reason,
            "independent_external_checksum": False,
        }

    metadata = {
        "exchange": exchange,
        "source_url": raw["source_url"],
        "filename": snapshot.name,
        "downloaded_at_utc": raw["downloaded_at_utc"],
        "trading_date": trading_date,
        "sha256": raw["sha256"],
    }

    return metadata, {
        "status": "PASS",
        "reason": "Provenance matches retained snapshot bytes.",
        "size_bytes_verified": True,
        "sha256_matches_retained_bytes": True,
        "redirect_chain_checked": True,
        # Downloader-generated hash is not an independent exchange hash.
        "independent_external_checksum": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("--nse-input", type=Path, required=True)
    parser.add_argument("--bse-input", type=Path, required=True)
    parser.add_argument("--nse-provenance", type=Path, required=True)
    parser.add_argument("--bse-provenance", type=Path)
    parser.add_argument("--nse-trading-date", required=True)
    parser.add_argument("--bse-trading-date", required=True)
    parser.add_argument(
        "--nse-cm-diagnostic",
        type=Path,
        action="append",
        default=[],
    )
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)

    args = parser.parse_args()

    for path in [args.nse_input, args.bse_input]:
        if not path.is_file():
            parser.error(f"Input file does not exist: {path}")

    for path in args.nse_cm_diagnostic:
        if not path.is_file():
            parser.error(f"Diagnostic file does not exist: {path}")

    try:
        nse_file_check = verify_snapshot_file(args.nse_input, "NSE")
        bse_file_check = verify_snapshot_file(args.bse_input, "BSE")
        nse, nse_load = load_nse_equity_universe(args.nse_input)
        bse, bse_load = load_bse_equity_universe(args.bse_input)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))

    nse_meta, nse_proof = load_snapshot_provenance(
        args.nse_input,
        args.nse_provenance,
        "NSE",
        args.nse_trading_date,
    )
    bse_meta, bse_proof = load_snapshot_provenance(
        args.bse_input,
        args.bse_provenance,
        "BSE",
        args.bse_trading_date,
    )

    detail, summary = build_exchange_universe_reconciliation(
        nse, bse, nse_meta, bse_meta
    )

    diagnostics = {
        "nse_equity_list": nse_load,
        "bse_security_master": bse_load,
        "snapshot_file_integrity": {
            "nse": nse_file_check,
            "bse": bse_file_check,
        },
        "provenance_verification": {
            "nse": nse_proof,
            "bse": bse_proof,
        },
    }

    if args.nse_cm_diagnostic:
        diagnostics["nse_cm_diagnostics"] = []
        for path in args.nse_cm_diagnostic:
            _, result = load_nse_cm_diagnostic(path)
            result["filename"] = path.name
            diagnostics["nse_cm_diagnostics"].append(result)

    # A successful identity reconciliation cannot override failed provenance.
    if nse_proof.get("status") != "PASS":
        summary["status"] = "REVIEW"
    if bse_proof.get("status") != "PASS":
        summary["status"] = "REVIEW"

    summary["production_provenance_approved"] = False
    summary["independent_external_checksum_verified"] = False
    summary["mapping_eligible"] = False
    summary["sector_mapping_activated"] = False

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
            "Downloader-generated SHA-256 is checked against retained bytes, not an independent exchange checksum.",
            "BSE production access and authorization remain unverified.",
            "A passing synthetic test does not establish real NSE/BSE universe coverage.",
            "Sector mapping remains OFF.",
        ],
    }

    (args.output_dir / "exchange_universe_summary.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps(payload, indent=2, ensure_ascii=False))

    if summary["status"] != "PASS":
        raise SystemExit("REVIEW: provenance or identity checks require resolution.")

    print("Exchange identity and supplied provenance checks: PASS")
    print("Production approval: HOLD")
    print("Sector Mapping remains OFF.")


if __name__ == "__main__":
    main()
        
