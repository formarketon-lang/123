
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
            str(c).replace("\ufeff", "").strip().upper().split()
        )
        for c in frame.columns
    ]
    return frame


def normalize_key_columns(frame):
    frame = frame.copy()

    for column in ["TCKRSYMB", "SCTYSRS", "ISIN"]:
        if column in frame.columns:
            frame[column] = (
                frame[column].astype("string").str.strip().str.upper()
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
    normalized_keys = ["Symbol", "Series", "ISIN"]

    missing_keys = [
        key for key in raw_keys if key not in raw.columns
    ]
    if missing_keys:
        raise ValueError(
            f"Raw file missing key columns: {missing_keys}"
        )

    if raw.duplicated(subset=raw_keys).any():
        raise ValueError(
            "Raw MII file contains duplicate Symbol/Series/ISIN keys."
        )

    raw = raw.set_index(raw_keys, drop=False)

    results = {}
    total_mismatches = 0

    for source_field, target_field in FIELD_MAPPING.items():

        if (
            source_field not in raw.columns
            or target_field not in normalized.columns
        ):
            results[source_field] = {
                "normalized_field": target_field,
                "status": "MISSING_COLUMN",
                "mismatch_count": None,
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

            if pd.isna(expected) and pd.isna(actual):
                compared += 1
                continue

            if pd.isna(expected) != pd.isna(actual):
                mismatches.append({
                    "key": key,
                    "raw_value": str(expected),
                    "normalized_value": str(actual),
                })
            elif target_field in ["Face Value", "Issued Capital"]:
                if float(expected) != float(actual):
                    mismatches.append({
                        "key": key,
                        "raw_value": str(expected),
                        "normalized_value": str(actual),
                    })
                else:
                    compared += 1
            elif target_field == "Listing Date":
                if pd.Timestamp(expected) != pd.Timestamp(actual):
                    mismatches.append({
                        "key": key,
                        "raw_value": str(expected),
                        "normalized_value": str(actual),
                    })
                else:
                    compared += 1
            elif str(expected) != str(actual):
                mismatches.append({
                    "key": key,
                    "raw_value": str(expected),
                    "normalized_value": str(actual),
                })
            else:
                compared += 1

        mismatch_count = len(mismatches)
        total_mismatches += mismatch_count

        results[source_field] = {
            "normalized_field": target_field,
            "status": "PASS" if mismatch_count == 0 else "MISMATCH",
            "compared_records": compared,
            "mismatch_count": mismatch_count,
            "mismatch_samples": mismatches[:10],
        }

    return results, total_mismatches


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

        if not (universe["Series"] == "EQ").all():
            raise ValueError("Non-EQ security found.")

        if not (universe["Delete Flag"] == "N").all():
            raise ValueError("Deleted security found.")

        if not (
            universe["Normal Market Eligibility"] == "1"
        ).all():
            raise ValueError("Ineligible security found.")

        if (
            universe["Normal Market Status"] == "3"
        ).any():
            raise ValueError("Suspended security found.")

        if not universe["ISIN"].str.fullmatch(
            r"IN[A-Z0-9]{10}", na=False
        ).all():
            raise ValueError("Invalid ISIN found.")

        if universe.duplicated(
            subset=["Symbol", "Series", "ISIN"]
        ).any():
            raise ValueError("Duplicate normalized security found.")

        if "MARICO" not in set(universe["Symbol"]):
            raise ValueError("MARICO not found.")

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

        mapping_report = {
            "audit_id": audit_id,
            "raw_source_url": capture["url"],
            "raw_file": raw_path.name,
            "raw_is_gzip": is_gzip,
            "raw_rows": int(len(raw_frame)),
            "normalized_rows": int(len(universe)),
            "field_mapping": mapping_results,
            "total_field_mismatches": total_mismatches,
            "status": (
                "PASS" if total_mismatches == 0 else "FAIL"
            ),
        }

        mapping_path.write_text(
            json.dumps(mapping_report, indent=2, default=str),
            encoding="utf-8",
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
            "unique_symbols": int(universe["Symbol"].nunique()),
            "marico_found": True,
            "permitted_to_trade_counts": (
                universe["Permitted to Trade"]
                .value_counts(dropna=False)
                .to_dict()
                if "Permitted to Trade" in universe.columns
                else {}
            ),
            "field_mismatches": total_mismatches,
            "status": (
                "PASS" if total_mismatches == 0 else "FAIL"
            ),
        }

        summary_path.write_text(
            json.dumps(summary, indent=2, default=str),
            encoding="utf-8",
        )

        print(json.dumps(summary, indent=2, default=str))

        if total_mismatches:
            raise ValueError(
                f"Field mapping mismatches found: {total_mismatches}"
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
