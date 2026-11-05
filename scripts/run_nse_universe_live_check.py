
import gzip
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from data.providers.nse_universe import fetch_nse_equity_universe

REPORT_DIR = PROJECT_ROOT / "reports" / "nse_universe_live"

FIELD_MAPPING = {
    "TCKRSYMB": "Symbol",
    "FININSTRMNM": "Company",
    "SCTYSRS": "Series",
    "LISTGDT": "Listing Date",
    "ISIN": "ISIN",
    "PARVAL": "Face Value",
    "ISSDCPTL": "Issued Capital",
    "DELFLG": "Delete Flag",
    "ELGBLTYNRMLMKT": "Normal Market Eligibility",
    "SCTYSTSNRMLMKT": "Normal Market Status",
    "PRTDTOTRAD": "Permitted to Trade",
}


class AuditedSession(requests.Session):
    """Capture the successful NSE MII response."""

    def __init__(self):
        super().__init__()
        self.requested_urls = []
        self.raw_responses = []

    def get(self, url, *args, **kwargs):
        self.requested_urls.append(url)
        response = super().get(url, *args, **kwargs)

        if (
            "/content/cm/NSE_CM_security_" in url
            and response.status_code == 200
            and response.content
        ):
            self.raw_responses.append({
                "url": url,
                "content": response.content,
                "content_type": response.headers.get("Content-Type"),
                "content_encoding": response.headers.get(
                    "Content-Encoding"
                ),
            })

        return response


def clean_columns(frame):
    frame = frame.copy()
    frame.columns = [
        " ".join(
            str(column)
            .replace("\ufeff", "")
            .strip()
            .upper()
            .split()
        )
        for column in frame.columns
    ]
    return frame


def normalize_key_columns(frame):
    frame = frame.copy()

    for column in ["TCKRSYMB", "SCTYSRS", "ISIN"]:
        if column in frame.columns:
            frame[column] = (
                frame[column]
                .astype("string")
                .str.strip()
                .str.upper()
            )

    return frame


def expected_normalized_values(raw_series, field):
    values = raw_series.astype("string").str.strip()

    if field in ["Symbol", "Series", "ISIN"]:
        return values.str.upper()

    if field == "Listing Date":
        seconds = pd.to_numeric(values, errors="coerce")

        dates = pd.to_datetime(
            seconds,
            unit="s",
            origin="1980-01-01",
            errors="coerce",
        )

        dates.loc[seconds.eq(0)] = pd.NaT
        return dates

    if field in ["Face Value", "Issued Capital"]:
        return pd.to_numeric(values, errors="coerce")

    return values


def compare_fields(raw_frame, normalized):
    raw = normalize_key_columns(raw_frame)
    normalized = normalized.copy()

    raw_keys = ["TCKRSYMB", "SCTYSRS", "ISIN"]

    missing_keys = [
        key for key in raw_keys
        if key not in raw.columns
    ]

    if missing_keys:
        raise ValueError(
            f"Raw file missing key columns: {missing_keys}"
        )

    normalized_keys = ["Symbol", "Series", "ISIN"]

    missing_normalized_keys = [
        key for key in normalized_keys
        if key not in normalized.columns
    ]

    if missing_normalized_keys:
        raise ValueError(
            "Normalized file missing key columns: "
            f"{missing_normalized_keys}"
        )

    if raw[raw_keys].isna().any().any():
        raise ValueError("Raw file contains null security keys.")

    if normalized[normalized_keys].isna().any().any():
        raise ValueError(
            "Normalized file contains null security keys."
        )

    if raw.duplicated(subset=raw_keys).any():
        raise ValueError(
            "Raw MII file contains duplicate "
            "Symbol/Series/ISIN keys."
        )

    if normalized.duplicated(subset=normalized_keys).any():
        raise ValueError(
            "Normalized file contains duplicate "
            "Symbol/Series/ISIN keys."
        )

    raw = raw.set_index(raw_keys, drop=False)

    results = {}
    total_mismatches = 0

    for source_field, target_field in FIELD_MAPPING.items():

        source_present = source_field in raw.columns
        target_present = target_field in normalized.columns

        # Missing mapped columns are a hard failure.
        if not source_present or not target_present:
            total_mismatches += 1

            results[source_field] = {
                "normalized_field": target_field,
                "status": "MISSING_COLUMN",
                "compared_records": 0,
                "mismatch_count": 1,
                "mismatch_samples": [{
                    "reason": (
                        "MAPPED_SOURCE_OR_TARGET_COLUMN_MISSING"
                    ),
                    "raw_column": source_field,
                    "normalized_column": target_field,
                    "raw_column_present": source_present,
                    "normalized_column_present": target_present,
                }],
            }
            continue

        mismatches = []
        compared = 0

        for _, row in normalized.iterrows():
            key = (
                str(row["Symbol"]).strip().upper(),
                str(row["Series"]).strip().upper(),
                str(row["ISIN"]).strip().upper(),
            )

            if key not in raw.index:
                mismatches.append({
                    "key": key,
                    "reason": "RAW_RECORD_NOT_FOUND",
                })
                continue

            raw_row = raw.loc[key]

            expected = expected_normalized_values(
                pd.Series([raw_row[source_field]]),
                target_field,
            ).iloc[0]

            actual = row[target_field]

            expected_missing = pd.isna(expected)
            actual_missing = pd.isna(actual)

            if expected_missing and actual_missing:
                compared += 1
                continue

            if expected_missing != actual_missing:
                mismatches.append({
                    "key": key,
                    "raw_value": str(expected),
                    "normalized_value": str(actual),
                    "reason": "NULL_VALUE_MISMATCH",
                })
                continue

            if target_field in ["Face Value", "Issued Capital"]:
                try:
                    equal = float(expected) == float(actual)
                except (TypeError, ValueError):
                    equal = False

            elif target_field == "Listing Date":
                equal = (
                    pd.Timestamp(expected)
                    == pd.Timestamp(actual)
                )

            else:
                equal = str(expected) == str(actual)

            if equal:
                compared += 1
            else:
                mismatches.append({
                    "key": key,
                    "raw_value": str(expected),
                    "normalized_value": str(actual),
                    "reason": "VALUE_MISMATCH",
                })

        mismatch_count = len(mismatches)
        total_mismatches += mismatch_count

        results[source_field] = {
            "normalized_field": target_field,
            "status": (
                "PASS" if mismatch_count == 0 else "MISMATCH"
            ),
            "compared_records": compared,
            "mismatch_count": mismatch_count,
            "mismatch_samples": mismatches[:10],
        }

    return results, total_mismatches


def validate_universe(universe):
    required = [
        "Symbol",
        "Company",
        "Series",
        "ISIN",
        "Delete Flag",
        "Normal Market Eligibility",
        "Normal Market Status",
        "Source",
    ]

    missing = [
        column for column in required
        if column not in universe.columns
    ]

    if missing:
        raise ValueError(
            f"Normalized columns missing: {missing}"
        )

    if universe.empty:
        raise ValueError("Normalized universe is empty.")

    if not universe["Series"].eq("EQ").all():
        raise ValueError("Non-EQ security found.")

    if not universe["Delete Flag"].eq("N").all():
        raise ValueError("Deleted security found.")

    if not universe[
        "Normal Market Eligibility"
    ].eq("1").all():
        raise ValueError("Ineligible security found.")

    if universe[
        "Normal Market Status"
    ].eq("3").any():
        raise ValueError("Suspended security found.")

    if not universe["ISIN"].str.fullmatch(
        r"IN[A-Z0-9]{10}",
        na=False,
    ).all():
        raise ValueError("Invalid ISIN found.")

    if universe.duplicated(
        subset=["Symbol", "Series", "ISIN"]
    ).any():
        raise ValueError("Duplicate normalized security found.")

    if "MARICO" not in set(universe["Symbol"]):
        raise ValueError("MARICO not found.")


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    audit_time = datetime.now(timezone.utc)
    audit_id = audit_time.strftime("%Y%m%d_%H%M%S")

    session = AuditedSession()

    try:
        print("========== NSE MII RAW FIELD AUDIT ==========")

        universe = fetch_nse_equity_universe(
            timeout=45,
            session=session,
            lookback_days=7,
        )

        if not session.raw_responses:
            raise ValueError(
                "Successful raw NSE MII response was not captured."
            )

        capture = session.raw_responses[-1]
        raw_bytes = capture["content"]

        is_gzip = raw_bytes[:2] == b"\x1f\x8b"

        if is_gzip:
            raw_path = REPORT_DIR / (
                f"nse_mii_raw_{audit_id}.csv.gz"
            )
            raw_path.write_bytes(raw_bytes)
            csv_bytes = gzip.decompress(raw_bytes)
        else:
            raw_path = REPORT_DIR / (
                f"nse_mii_raw_{audit_id}.csv"
            )
            raw_path.write_bytes(raw_bytes)
            csv_bytes = raw_bytes

        raw_frame = pd.read_csv(
            io.BytesIO(csv_bytes),
            dtype="string",
            low_memory=False,
        )

        raw_frame = clean_columns(raw_frame)

        validate_universe(universe)

        mapping_results, total_mismatches = compare_fields(
            raw_frame,
            universe,
        )

        normalized_path = REPORT_DIR / (
            f"nse_universe_{audit_id}.csv"
        )

        mapping_path = REPORT_DIR / (
            f"nse_field_mapping_{audit_id}.json"
        )

        summary_path = REPORT_DIR / (
            f"nse_universe_{audit_id}.json"
        )

        universe.to_csv(normalized_path, index=False)

        mapping_status = (
            "PASS" if total_mismatches == 0 else "FAIL"
        )

        mapping_report = {
            "audit_id": audit_id,
            "raw_source_url": capture["url"],
            "raw_file": raw_path.name,
            "raw_is_gzip": is_gzip,
            "content_type": capture["content_type"],
            "content_encoding": capture["content_encoding"],
            "raw_rows": int(len(raw_frame)),
            "normalized_rows": int(len(universe)),
            "field_mapping": mapping_results,
            "total_field_mismatches": total_mismatches,
            "status": mapping_status,
        }

        mapping_path.write_text(
            json.dumps(
                mapping_report,
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )

        permitted_counts = {}

        if "Permitted to Trade" in universe.columns:
            permitted_counts = (
                universe["Permitted to Trade"]
                .value_counts(dropna=False)
                .to_dict()
            )

        summary = {
            "audit_id": audit_id,
            "audit_time_utc": audit_time.isoformat(),
            "source": "NSE MII Security Master",
            "source_url": capture["url"],
            "raw_file": raw_path.name,
            "normalized_file": normalized_path.name,
            "mapping_file": mapping_path.name,
            "raw_rows": int(len(raw_frame)),
            "normalized_rows": int(len(universe)),
            "unique_symbols": int(
                universe["Symbol"].nunique()
            ),
            "marico_found": True,
            "permitted_to_trade_counts": permitted_counts,
            "field_mismatches": total_mismatches,
            "mapping_status": mapping_status,
            "status": (
                "PASS"
                if total_mismatches == 0
                else "FAIL"
            ),
        }

        summary_path.write_text(
            json.dumps(
                summary,
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )

        print(json.dumps(summary, indent=2, default=str))

        if total_mismatches:
            raise ValueError(
                "Field mapping mismatches found: "
                f"{total_mismatches}"
            )

        print("NSE MII RAW FIELD AUDIT: PASS")

    except Exception as error:
        print("NSE MII RAW FIELD AUDIT: FAIL")
        print(f"{type(error).__name__}: {error}")
        raise

    finally:
        session.close()


if __name__ == "__main__":
    main()
    