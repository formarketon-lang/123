
"""Capture and audit one dated official NSE MII cash-equity snapshot."""

from __future__ import annotations

import argparse
import json
import sys

from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.providers.exchange_snapshot_downloader import (  # noqa: E402
    download_exchange_snapshot,
)
from data.providers.nse_universe import (  # noqa: E402
    NSE_HEADERS,
    NSE_MII_SECURITY_URL_TEMPLATE,
    normalize_nse_mii_security_master,
)
from scripts.run_exchange_universe_reconciliation import (  # noqa: E402
    load_snapshot_provenance,
)

DEFAULT_OUTPUT = ROOT / "reports" / "nse_dated_snapshot_audit"


def validate_normalized_universe(frame: pd.DataFrame) -> None:
    required = {
        "Symbol",
        "Company",
        "Series",
        "ISIN",
        "Delete Flag",
        "Normal Market Eligibility",
        "Normal Market Status",
    }
    missing = sorted(required.difference(frame.columns))

    if missing:
        raise ValueError(f"Missing normalized fields: {missing}")

    if frame.empty:
        raise ValueError("NSE normalized universe is empty.")

    if not frame["Series"].eq("EQ").all():
        raise ValueError("Non-EQ record found.")

    if not frame["Delete Flag"].eq("N").all():
        raise ValueError("Deleted security found.")

    if not frame["Normal Market Eligibility"].eq("1").all():
        raise ValueError("Ineligible security found.")

    if frame["Normal Market Status"].eq("3").any():
        raise ValueError("Suspended security found.")

    if not frame["ISIN"].str.fullmatch(
        r"IN[A-Z0-9]{10}", na=False
    ).all():
        raise ValueError("Invalid Indian ISIN found.")

    if frame.duplicated(
        subset=["Symbol", "Series", "ISIN"]
    ).any():
        raise ValueError("Duplicate security identity found.")


def run_nse_dated_snapshot_audit(
    archive_date: date,
    output_dir: Path = DEFAULT_OUTPUT,
    *,
    session: requests.Session | None = None,
    timeout: int = 45,
) -> dict:
    if not isinstance(archive_date, date):
        raise TypeError("archive_date must be datetime.date.")

    date_token = archive_date.strftime("%d%m%Y")
    source_url = NSE_MII_SECURITY_URL_TEMPLATE.format(
        date=date_token
    )

    audit_id = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )
    audit_dir = Path(output_dir) / (
        f"{archive_date.isoformat()}_{audit_id}"
    )
    audit_dir.mkdir(parents=True, exist_ok=False)

    snapshot = audit_dir / (
        f"NSE_CM_security_{date_token}.csv.gz"
    )

    client = session or requests.Session()
    client.headers.update(NSE_HEADERS)

    try:
        download_metadata = download_exchange_snapshot(
            "NSE",
            source_url,
            snapshot,
            session=client,
            timeout=timeout,
        )
    finally:
        if session is None:
            client.close()

    provenance_path = snapshot.with_name(
        snapshot.name + ".provenance.json"
    )

    provenance_metadata, provenance_check = (
        load_snapshot_provenance(
            snapshot,
            provenance_path,
            "NSE",
            archive_date.isoformat(),
        )
    )

    if provenance_check.get("status") != "PASS":
        raise ValueError(
            "NSE provenance verification failed: "
            + str(provenance_check.get("reason"))
        )

    if provenance_metadata.get("source_url") != source_url:
        raise ValueError(
            "Downloaded source URL does not match requested archive date."
        )

    raw = pd.read_csv(
        snapshot,
        compression="gzip",
        dtype="string",
        low_memory=False,
    )

    normalized = normalize_nse_mii_security_master(raw)
    validate_normalized_universe(normalized)

    normalized["Universe As Of Date"] = pd.Timestamp(archive_date)
    normalized["Universe Verification Status"] = "MII_DATED"

    normalized_path = audit_dir / "nse_normalized_universe.csv"
    normalized.to_csv(normalized_path, index=False)

    summary = {
        "audit_id": audit_id,
        "status": "PASS",
        "exchange": "NSE",
        "source": "NSE MII Security Master",
        "source_url": source_url,
        "archive_date": archive_date.isoformat(),
        "raw_snapshot": snapshot.name,
        "raw_sha256": download_metadata["sha256"],
        "raw_size_bytes": download_metadata["size_bytes"],
        "normalized_file": normalized_path.name,
        "normalized_rows": int(len(normalized)),
        "unique_symbols": int(normalized["Symbol"].nunique()),
        "unique_isins": int(normalized["ISIN"].nunique()),
        "provenance_check": provenance_check,
        "bse_status": "REVIEW",
        "independent_external_checksum_verified": False,
        "sector_mapping_activated": False,
        "broker_api_dependency": False,
    }

    summary_path = audit_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("NSE DATED SNAPSHOT AUDIT: PASS")
    print("BSE: REVIEW | SECTOR MAPPING: OFF")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--as-of-date",
        required=True,
        help="NSE archive date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
    )
    args = parser.parse_args()

    try:
        archive_date = date.fromisoformat(args.as_of_date)
    except ValueError:
        parser.error("--as-of-date must use YYYY-MM-DD.")

    run_nse_dated_snapshot_audit(
        archive_date,
        args.output_dir,
    )


if __name__ == "__main__":
    main()
  
