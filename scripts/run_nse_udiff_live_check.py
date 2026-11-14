"""One-off live verification of the official NSE CM UDiFF ingestion path."""

from __future__ import annotations

import gzip
import hashlib
import json
import sys
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from openpyxl import load_workbook
from zipfile import BadZipFile, ZipFile

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
from data.providers.nse_universe import (
    NSE_HEADERS,
    NSE_MII_SECURITY_URL_TEMPLATE,
    fetch_nse_equity_universe,
)


NSE_UDIFF_SCHEMA_WORKBOOK_URL = (
    "https://nsearchives.nseindia.com/web/mediaattachment/2026-06/"
    "UDiFF_trade_and_Bhavcopy_file_formats_20260630115803.xlsx"
)
NSE_UDIFF_OFFICIAL_SAMPLE_URL = (
    "https://nsearchives.nseindia.com/web/sites/default/files/"
    "inline-files/Bhavcopy.zip"
)
REQUIRED_UDIFF_TAGS = {
    "TradDt",
    "Sgmt",
    "Src",
    "FinInstrmTp",
    "FinInstrmId",
    "SsnId",
    "ISIN",
    "TckrSymb",
    "SctySrs",
    "OpnPric",
    "HghPric",
    "LwPric",
    "ClsPric",
    "PrvsClsgPric",
    "TtlTradgVol",
}


EXPECTED_UDIFF_FIELD_TAGS = {
    "Trade Date": "TradDt",
    "Segment Indicator": "Sgmt",
    "Source": "Src",
    "Instrument Type": "FinInstrmTp",
    "Unique Instrument Identifier Of Trading Exchange": "FinInstrmId",
    "Instrument ISIN": "ISIN",
    "Instrument Symbol or Scrip Code": "TckrSymb",
    "Instrument Series": "SctySrs",
    "Open": "OpnPric",
    "High": "HghPric",
    "Low": "LwPric",
    "Close": "ClsPric",
    "Previous Close": "PrvsClsgPric",
    "Total Traded Qty": "TtlTradgVol",
    "Session Id": "SsnId",
}


def verify_official_udiff_schema(output_dir: Path) -> dict:
    """Cross-check production tags against NSE's official workbook and sample."""

    evidence = {
        "workbook_url": NSE_UDIFF_SCHEMA_WORKBOOK_URL,
        "sample_url": NSE_UDIFF_OFFICIAL_SAMPLE_URL,
        "workbook_status": "REVIEW",
        "sample_status": "REVIEW",
        "schema_mapping_status": "REVIEW",
        "required_tags": sorted(REQUIRED_UDIFF_TAGS),
    }

    workbook_bytes = None
    try:
        response = requests.get(
            NSE_UDIFF_SCHEMA_WORKBOOK_URL,
            headers=NSE_HEADERS,
            timeout=45,
        )
        response.raise_for_status()
        final_url = response.url or NSE_UDIFF_SCHEMA_WORKBOOK_URL
        if (
            final_url.startswith("https://")
            and "nsearchives.nseindia.com" in final_url
        ):
            workbook_bytes = response.content
            workbook_path = output_dir / "nse_udiff_format_workbook.xlsx"
            workbook_path.write_bytes(workbook_bytes)
            evidence["workbook_sha256"] = hashlib.sha256(
                workbook_bytes
            ).hexdigest()

            workbook = load_workbook(
                BytesIO(workbook_bytes),
                read_only=True,
                data_only=True,
            )
            evidence["workbook_sheets"] = list(workbook.sheetnames)
            candidates = []

            mapping_checks = {}
            for sheet in workbook.worksheets:
                rows = list(sheet.iter_rows(values_only=True))
                flattened = {
                    str(value).strip()
                    for row in rows
                    for value in row
                    if value is not None
                }
                if not REQUIRED_UDIFF_TAGS.issubset(flattened):
                    continue

                sheet_mapping = {}
                for row in rows:
                    if len(row) < 4:
                        continue
                    field_name = row[1]
                    iso_tag = row[3]
                    if field_name is None or iso_tag is None:
                        continue
                    sheet_mapping[
                        " ".join(str(field_name).strip().split()).casefold()
                    ] = str(iso_tag).strip()

                expected_mapping = {
                    " ".join(field.split()).casefold(): tag
                    for field, tag in EXPECTED_UDIFF_FIELD_TAGS.items()
                }
                mismatches = {
                    field: {
                        "expected": tag,
                        "observed": sheet_mapping.get(field),
                    }
                    for field, tag in expected_mapping.items()
                    if sheet_mapping.get(field) != tag
                }
                mapping_checks[sheet.title] = {
                    "mismatches": mismatches,
                    "mapping_status": (
                        "PASS" if not mismatches else "REVIEW"
                    ),
                }
                candidates.append(sheet.title)

            evidence["matching_bhavcopy_sheets"] = [
                name for name in candidates
                if "bhav" in name.lower()
            ]
            evidence["matching_sheets"] = candidates
            evidence["field_mapping_checks"] = mapping_checks
            selected_sheets = evidence["matching_bhavcopy_sheets"]
            evidence["workbook_status"] = (
                "PASS"
                if any(
                    mapping_checks[name]["mapping_status"] == "PASS"
                    for name in selected_sheets
                )
                else "REVIEW"
            )
            workbook.close()
    except Exception as exc:
        evidence["workbook_error"] = (
            f"{type(exc).__name__}: {exc}"
        )

    try:
        response = requests.get(
            NSE_UDIFF_OFFICIAL_SAMPLE_URL,
            headers=NSE_HEADERS,
            timeout=45,
        )
        response.raise_for_status()
        sample_bytes = response.content
        sample_path = output_dir / "nse_udiff_official_bhavcopy_sample.zip"
        sample_path.write_bytes(sample_bytes)
        evidence["sample_sha256"] = hashlib.sha256(
            sample_bytes
        ).hexdigest()

        matching_members = []
        try:
            with ZipFile(BytesIO(sample_bytes)) as archive:
                corrupt_member = archive.testzip()
                if corrupt_member is not None:
                    raise BadZipFile(
                        f"Corrupt sample member: {corrupt_member}"
                    )
                for member in archive.namelist():
                    if not member.lower().endswith(".csv"):
                        continue
                    sample_frame = pd.read_csv(
                        BytesIO(archive.read(member)),
                        nrows=0,
                        dtype="string",
                    )
                    tags = {
                        str(column).strip()
                        for column in sample_frame.columns
                    }
                    if REQUIRED_UDIFF_TAGS.issubset(tags):
                        matching_members.append(member)
        except BadZipFile:
            raise

        evidence["matching_sample_members"] = matching_members
        evidence["sample_status"] = (
            "PASS" if matching_members else "REVIEW"
        )
    except Exception as exc:
        evidence["sample_error"] = (
            f"{type(exc).__name__}: {exc}"
        )

    if (
        evidence["workbook_status"] == "PASS"
        and evidence["sample_status"] == "PASS"
    ):
        evidence["schema_mapping_status"] = "PASS"

    (output_dir / "nse_udiff_schema_evidence.json").write_text(
        json.dumps(evidence, indent=2),
        encoding="utf-8",
    )
    return evidence


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

    output_dir = Path("artifacts/nse_udiff_live")
    output_dir.mkdir(parents=True, exist_ok=True)
    schema_evidence = verify_official_udiff_schema(output_dir)

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

    # Preserve raw MII rows for any symbol rejected by the normalized
    # eligibility rules. This makes identity exceptions auditable.
    mii_url = NSE_MII_SECURITY_URL_TEMPLATE.format(
        date=selected_date.strftime("%d%m%Y")
    )
    raw_mii_response = requests.get(
        mii_url,
        headers=NSE_HEADERS,
        timeout=30,
    )
    raw_mii_response.raise_for_status()
    raw_mii_bytes = raw_mii_response.content
    if raw_mii_bytes[:2] == b"\x1f\x8b":
        raw_mii_bytes = gzip.decompress(raw_mii_bytes)
    raw_mii = pd.read_csv(
        BytesIO(raw_mii_bytes),
        dtype="string",
        low_memory=False,
    )
    raw_mii.columns = [str(c).strip().upper() for c in raw_mii.columns]
    mii_identity = universe.set_index("Symbol")
    mii_isin_by_symbol = mii_identity["ISIN"].to_dict()
    mii_instrument_id_by_symbol = (
        mii_identity["Instrument ID"].to_dict()
    )
    normalized = downloaded["normalized"]
    diagnostic_symbols = set()

    for symbol_value, isin_value, instrument_id_value in normalized[
        ["Symbol", "ISIN", "Instrument ID"]
    ].itertuples(index=False, name=None):
        symbol = str(symbol_value).strip().upper()
        isin = str(isin_value).strip().upper()
        instrument_id = str(instrument_id_value).strip().upper()
        if symbol not in mii_isin_by_symbol:
            diagnostic_symbols.add(symbol)
        elif (
            isin != str(mii_isin_by_symbol[symbol]).strip().upper()
            or instrument_id
            != str(mii_instrument_id_by_symbol[symbol]).strip().upper()
        ):
            diagnostic_symbols.add(symbol)

    raw_mii_symbol_column = "TCKRSYMB"
    if raw_mii_symbol_column in raw_mii.columns:
        raw_mii_diag = raw_mii[
            raw_mii[raw_mii_symbol_column]
            .astype("string")
            .str.strip()
            .str.upper()
            .isin(diagnostic_symbols)
        ].copy()
    else:
        raw_mii_diag = pd.DataFrame()
    raw_udiff_diag = downloaded["raw_data"][
        downloaded["raw_data"]["TckrSymb"]
        .astype("string")
        .str.strip()
        .str.upper()
        .isin(diagnostic_symbols)
    ].copy()
    raw_mii_diag.to_csv(
        output_dir / "mii_identity_exception_raw_diagnostic.csv",
        index=False,
    )
    raw_udiff_diag.to_csv(
        output_dir / "udiff_identity_exception_raw_diagnostic.csv",
        index=False,
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
        schema_mapping_verified=(
            schema_evidence["schema_mapping_status"] == "PASS"
        ),
    )

    report = {
        "ingestion_status": "PASS",
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
        "unknown_symbols": reconciliation["unknown_symbols"],
        "unknown_symbol_count": reconciliation["unknown_count"],
        "isin_mismatch_symbols": reconciliation["isin_mismatch_symbols"],
        "isin_mismatch_count": reconciliation["isin_mismatch_count"],
        "instrument_id_mismatch_symbols": reconciliation[
            "instrument_id_mismatch_symbols"
        ],
        "instrument_id_mismatch_count": reconciliation[
            "instrument_id_mismatch_count"
        ],
        "identity_exceptions": reconciliation["identity_exceptions"],
        "coverage_status": reconciliation["coverage_status"],
        "coverage_pct": reconciliation["coverage_pct"],
        "missing_symbol_count": reconciliation["missing_count"],
        "audit_status": audit["audit_status"],
        "source_authenticity_status": audit[
            "source_authenticity_status"
        ],
        "schema_mapping_status": audit["schema_mapping_status"],
        "official_schema_evidence": schema_evidence,
        "audit_reasons": audit["audit_reasons"],
        "udiff_dcmfinserv_rows": len(raw_udiff_diag),
        "mii_dcmfinserv_raw_rows": len(raw_mii_diag),
        "mii_dcmfinserv_raw": raw_mii_diag.to_dict(orient="records"),
    }

    (output_dir / "nse_udiff_live_audit.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print("NSE UDiFF live download: PASS")
    print("Official raw ISO fields: PASS")
    print(f"NSE MII identity: {report['identity_status']}")
    print(f"Unknown MII symbols: {report['unknown_symbols']}")
    print(
        "Symbol/ISIN mismatches: "
        f"{report['isin_mismatch_symbols']}"
    )
    print(
        "Instrument ID mismatches: "
        f"{report['instrument_id_mismatch_symbols']}"
    )
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
