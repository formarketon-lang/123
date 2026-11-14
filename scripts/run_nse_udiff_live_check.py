"""One-off live verification of the official NSE CM UDiFF ingestion path."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.providers.nse_bhavcopy_mii_validation import (
    reconcile_bhavcopy_with_mii,
)
from data.providers.nse_bhavcopy_provenance import (
    NSE_UDIFF_SCHEMA_REFERENCE_URL,
    audit_nse_bhavcopy_provenance,
)
from data.providers.nse_udiff_downloader import (
    NSEUdiFFDownloadError,
    download_nse_cm_udiff_equity_bhavcopy,
)
from data.providers.nse_universe import fetch_nse_equity_universe


def main() -> None:
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    downloaded = None
    selected_date = None
    failures = []

    for offset in range(1, 8):
        candidate = today - timedelta(days=offset)
        if candidate.weekday() >= 5:
            continue

        try:
            downloaded = download_nse_cm_udiff_equity_bhavcopy(candidate)
            selected_date = candidate
            break
        except NSEUdiFFDownloadError as exc:
            failures.append(f"{candidate.isoformat()}: {exc}")

    if downloaded is None or selected_date is None:
        raise RuntimeError(
            "No official NSE CM UDiFF final file was available in the "
            "last seven calendar days. " + " | ".join(failures)
        )

    universe = fetch_nse_equity_universe(
        as_of_date=selected_date,
        lookback_days=0,
    )

    if (
        universe.empty
        or "Universe Verification Status" not in universe.columns
        or not universe["Universe Verification Status"]
        .astype("string")
        .str.upper()
        .eq("MII_DATED")
        .all()
    ):
        raise RuntimeError(
            "A date-matched official NSE MII snapshot is required; "
            "legacy/undated fallback is not accepted."
        )

    reconciliation = reconcile_bhavcopy_with_mii(
        downloaded["normalized"],
        universe,
    )

    audit = audit_nse_bhavcopy_provenance(
        bhavcopy=downloaded["normalized"],
        universe=universe,
        source_bytes=downloaded["raw_bytes"],
        source_filename=downloaded["source_filename"],
        source_url=downloaded["source_url"],
        schema_reference_url=NSE_UDIFF_SCHEMA_REFERENCE_URL,
    )

    output_dir = Path("artifacts/nse_udiff_live")
    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / downloaded["source_filename"]).write_bytes(
        downloaded["raw_bytes"]
    )
    downloaded["normalized"].to_csv(
        output_dir / "nse_udiff_equity_normalized.csv",
        index=False,
    )
    universe.to_csv(
        output_dir / "nse_mii_universe.csv",
        index=False,
    )

    report = {
        "workflow_status": "PASS",
        "observation_date": selected_date.isoformat(),
        "source": downloaded["source"],
        "source_url": downloaded["source_url"],
        "source_filename": downloaded["source_filename"],
        "source_sha256": downloaded["sha256"],
        "fetched_at_utc": downloaded["fetched_at_utc"],
        "raw_row_count": len(downloaded["raw_data"]),
        "raw_columns": list(downloaded["raw_data"].columns),
        "normalized_eq_row_count": len(downloaded["normalized"]),
        "mii_universe_row_count": len(universe),
        "identity_status": reconciliation["identity_status"],
        "coverage_status": reconciliation["coverage_status"],
        "coverage_pct": reconciliation["coverage_pct"],
        "missing_symbol_count": reconciliation["missing_count"],
        "audit_status": audit["audit_status"],
        "source_authenticity_status": audit[
            "source_authenticity_status"
        ],
        "schema_mapping_status": audit["schema_mapping_status"],
        "audit_reasons": audit["audit_reasons"],
    }

    (output_dir / "nse_udiff_live_audit.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print("NSE UDiFF live download: PASS")
    print("Official raw ISO fields: PASS")
    print("NSE MII identity: PASS")
    print(f"Historical membership coverage: {report['coverage_status']}")
    print(f"Coverage: {report['coverage_pct']}%")
    print(f"Schema mapping: {report['schema_mapping_status']}")
    print(f"Audit: {report['audit_status']}")
    print(f"Observation date: {report['observation_date']}")
    print(f"Normalized EQ rows: {report['normalized_eq_row_count']}")
    print(f"SHA256: {report['source_sha256']}")

    # A REVIEW audit is expected until the official workbook's exact
    # Bhavcopy field sheet is independently reviewed and signed off.
    # Download, raw-field, and identity failures remain hard failures.


if __name__ == "__main__":
    main()
