"""Live audit of NSE MII raw security-master data vs normalized EQ universe."""

from __future__ import annotations

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

from data.providers.nse_universe import (  # noqa: E402
    fetch_nse_equity_universe,
)

REPORT_DIR = PROJECT_ROOT / "reports" / "nse_universe_live"

FIELD_MAPPING = {
    "FININSTRMID": "Instrument ID",
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

RAW_SCOPE_REQUIRED = [
    "TCKRSYMB",
    "FININSTRMNM",
    "SCTYSRS",
    "ISIN",
    "DELFLG",
    "ELGBLTYNRMLMKT",
    "SCTYSTSNRMLMKT",
]


class AuditedSession(requests.Session):
    """Capture the exact successful NSE MII response used by the provider."""

    def __init__(self):
        super().__init__()
        self.raw_responses = []

    def get(self, url, *args, **kwargs):
        response = super().get(url, *args, **kwargs)
        if (
            "/content/cm/NSE_CM_security_" in url
            and response.status_code == 200
            and response.content
        ):
            self.raw_responses.append(
                {
                    "url": url,
                    "content": response.content,
                    "content_type": response.headers.get("Content-Type"),
                    "content_encoding": response.headers.get("Content-Encoding"),
                }
            )
        return response


def clean_columns(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame.columns = [
        " ".join(
            str(column).replace("\ufeff", "").strip().upper().split()
        )
        for column in frame.columns
    ]
    return frame


def _text(frame: pd.DataFrame, column: str) -> pd.Series:
    return frame[column].astype("string").str.strip()


def prepare_raw_equity_scope(raw_frame: pd.DataFrame):
    """Apply the provider's NSE cash-EQ eligibility rules to raw MII rows.

    The raw MII file contains many non-EQ instruments and historical rows.
    Those rows are not members of the normalized cash-equity universe and
    must not be treated as malformed security keys during field comparison.
    """
    raw = clean_columns(raw_frame)
    missing = [c for c in RAW_SCOPE_REQUIRED if c not in raw.columns]
    if missing:
        raise ValueError(f"Raw MII file missing scope columns: {missing}")

    mask = _text(raw, "SCTYSRS").str.upper().eq("EQ")
    mask &= _text(raw, "DELFLG").str.upper().eq("N")
    mask &= _text(raw, "ELGBLTYNRMLMKT").eq("1")
    mask &= ~_text(raw, "SCTYSTSNRMLMKT").eq("3")

    if "PRTDTOTRAD" in raw.columns:
        # Match normalize_nse_mii_security_master(): exclude BSE-only code 2.
        mask &= ~_text(raw, "PRTDTOTRAD").eq("2")

    symbol = _text(raw, "TCKRSYMB")
    company = _text(raw, "FININSTRMNM")
    isin = _text(raw, "ISIN").str.upper()

    mask &= raw["TCKRSYMB"].notna() & symbol.ne("")
    mask &= raw["FININSTRMNM"].notna() & company.ne("")
    mask &= raw["ISIN"].notna() & isin.str.fullmatch(
        r"IN[A-Z0-9]{10}", na=False
    )
    mask &= ~symbol.str.upper().str.endswith("$", na=False)
    mask &= ~symbol.str.contains(
        r"NSETEST|DUMMY", case=False, regex=True, na=False
    )

    scoped = raw.loc[mask].copy()
    scoped = scoped.reset_index(drop=True)

    exclusion_summary = {
        "raw_rows": int(len(raw)),
        "eligible_eq_scope_rows": int(len(scoped)),
        "excluded_out_of_scope_rows": int(len(raw) - len(scoped)),
        "raw_null_key_rows_outside_scope": int(
            raw[["TCKRSYMB", "SCTYSRS", "ISIN"]].isna().any(axis=1).sum()
        ),
    }
    return scoped, exclusion_summary


def expected_normalized_values(raw_series: pd.Series, field: str):
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


def compare_fields(raw_frame: pd.DataFrame, normalized: pd.DataFrame):
    """Compare all mapped fields using a one-to-one key merge."""
    raw = clean_columns(raw_frame)
    normalized = normalized.copy()
    raw_keys = ["TCKRSYMB", "SCTYSRS", "ISIN"]
    normalized_keys = ["Symbol", "Series", "ISIN"]

    missing_raw = [key for key in raw_keys if key not in raw.columns]
    missing_normalized = [
        key for key in normalized_keys if key not in normalized.columns
    ]
    if missing_raw:
        raise ValueError(f"Scoped raw file missing key columns: {missing_raw}")
    if missing_normalized:
        raise ValueError(
            f"Normalized file missing key columns: {missing_normalized}"
        )

    raw = raw.copy()
    for key in raw_keys:
        raw[key] = _text(raw, key).str.upper()
    for key in normalized_keys:
        normalized[key] = (
            normalized[key].astype("string").str.strip().str.upper()
        )

    if raw[raw_keys].isna().any().any() or raw[raw_keys].eq("").any().any():
        raise ValueError("Eligible raw EQ scope contains null/blank security keys.")
    if normalized[normalized_keys].isna().any().any() or normalized[
        normalized_keys
    ].eq("").any().any():
        raise ValueError("Normalized universe contains null/blank security keys.")
    if raw.duplicated(subset=raw_keys).any():
        raise ValueError("Eligible raw EQ scope contains duplicate security keys.")
    if normalized.duplicated(subset=normalized_keys).any():
        raise ValueError("Normalized universe contains duplicate security keys.")

    raw_key_frame = raw[raw_keys].rename(
        columns={"TCKRSYMB": "Symbol", "SCTYSRS": "Series"}
    )
    normalized_key_frame = normalized[normalized_keys]
    key_merge = raw_key_frame.merge(
        normalized_key_frame,
        on=normalized_keys,
        how="outer",
        indicator=True,
        validate="one_to_one",
    )
    missing_from_normalized = key_merge.loc[
        key_merge["_merge"] == "left_only", normalized_keys
    ]
    missing_from_raw = key_merge.loc[
        key_merge["_merge"] == "right_only", normalized_keys
    ]
    key_coverage = {
        "raw_scope_keys": int(len(raw_key_frame)),
        "normalized_keys": int(len(normalized_key_frame)),
        "missing_from_normalized_count": int(len(missing_from_normalized)),
        "missing_from_raw_count": int(len(missing_from_raw)),
        "missing_from_normalized_samples": missing_from_normalized.head(10).values.tolist(),
        "missing_from_raw_samples": missing_from_raw.head(10).values.tolist(),
        "status": "PASS"
        if missing_from_normalized.empty and missing_from_raw.empty
        else "FAIL",
    }

    results = {}
    total_mismatches = (
        len(missing_from_normalized) + len(missing_from_raw)
    )

    for source_field, target_field in FIELD_MAPPING.items():
        source_present = source_field in raw.columns
        target_present = target_field in normalized.columns
        if not source_present or not target_present:
            total_mismatches += 1
            results[source_field] = {
                "normalized_field": target_field,
                "status": "MISSING_COLUMN",
                "compared_records": 0,
                "mismatch_count": 1,
                "mismatch_samples": [{
                    "reason": "MAPPED_SOURCE_OR_TARGET_COLUMN_MISSING",
                    "raw_column_present": source_present,
                    "normalized_column_present": target_present,
                }],
            }
            continue

        left = raw_key_frame.copy()
        left["__raw_value"] = raw[source_field].reset_index(drop=True)
        right = normalized[normalized_keys].copy()
        right["__normalized_value"] = normalized[target_field].reset_index(drop=True)
        joined = left.merge(
            right,
            on=normalized_keys,
            how="inner",
            validate="one_to_one",
        )

        expected = expected_normalized_values(
            joined["__raw_value"], target_field
        )
        actual = joined["__normalized_value"]

        if target_field in ["Face Value", "Issued Capital"]:
            expected = pd.to_numeric(expected, errors="coerce")
            actual = pd.to_numeric(actual, errors="coerce")
            equal_values = expected.eq(actual)
        elif target_field == "Listing Date":
            actual = pd.to_datetime(actual, errors="coerce")
            equal_values = expected.eq(actual)
        else:
            expected = expected.astype("string")
            actual = actual.astype("string")
            equal_values = expected.eq(actual)

        both_missing = expected.isna() & actual.isna()
        one_missing = expected.isna() ^ actual.isna()
        equal = (equal_values & ~one_missing) | both_missing
        mismatch_mask = ~equal
        mismatch_rows = joined.loc[mismatch_mask].copy()
        mismatch_rows["__expected"] = expected.loc[mismatch_mask].astype("string")
        mismatch_rows["__actual"] = actual.loc[mismatch_mask].astype("string")
        mismatch_samples = []
        for _, row in mismatch_rows.head(10).iterrows():
            mismatch_samples.append({
                "key": [row["Symbol"], row["Series"], row["ISIN"]],
                "raw_value": row["__expected"],
                "normalized_value": row["__actual"],
                "reason": "VALUE_MISMATCH",
            })

        mismatch_count = int(mismatch_mask.sum())
        total_mismatches += mismatch_count
        results[source_field] = {
            "normalized_field": target_field,
            "status": "PASS" if mismatch_count == 0 else "MISMATCH",
            "compared_records": int(equal.sum()),
            "mismatch_count": mismatch_count,
            "mismatch_samples": mismatch_samples,
        }

    return results, total_mismatches, key_coverage

def validate_universe(universe: pd.DataFrame):
    required = [
        "Symbol", "Company", "Series", "ISIN", "Delete Flag",
        "Normal Market Eligibility", "Normal Market Status", "Source",
    ]
    missing = [column for column in required if column not in universe.columns]
    if missing:
        raise ValueError(f"Normalized columns missing: {missing}")
    if universe.empty:
        raise ValueError("Normalized universe is empty.")
    if not universe["Series"].eq("EQ").all():
        raise ValueError("Non-EQ security found in normalized universe.")
    if not universe["Delete Flag"].eq("N").all():
        raise ValueError("Deleted security found in normalized universe.")
    if not universe["Normal Market Eligibility"].eq("1").all():
        raise ValueError("Ineligible security found in normalized universe.")
    if universe["Normal Market Status"].eq("3").any():
        raise ValueError("Suspended security found in normalized universe.")
    if not universe["ISIN"].str.fullmatch(r"IN[A-Z0-9]{10}", na=False).all():
        raise ValueError("Invalid ISIN found in normalized universe.")
    if universe.duplicated(subset=["Symbol", "Series", "ISIN"]).any():
        raise ValueError("Duplicate normalized security found.")
    if "MARICO" not in set(universe["Symbol"]):
        raise ValueError("MARICO not found in normalized universe.")


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    audit_time = datetime.now(timezone.utc)
    audit_id = audit_time.strftime("%Y%m%d_%H%M%S")
    session = AuditedSession()

    try:
        print("========== NSE MII RAW FIELD AUDIT ==========")
        universe = fetch_nse_equity_universe(
            timeout=45, session=session, lookback_days=7
        )
        if not session.raw_responses:
            raise ValueError("Successful raw NSE MII response was not captured.")

        capture = session.raw_responses[-1]
        raw_bytes = capture["content"]
        is_gzip = raw_bytes[:2] == b"\x1f\x8b"
        if is_gzip:
            raw_path = REPORT_DIR / f"nse_mii_raw_{audit_id}.csv.gz"
            raw_path.write_bytes(raw_bytes)
            csv_bytes = gzip.decompress(raw_bytes)
        else:
            raw_path = REPORT_DIR / f"nse_mii_raw_{audit_id}.csv"
            raw_path.write_bytes(raw_bytes)
            csv_bytes = raw_bytes

        raw_frame = pd.read_csv(
            io.BytesIO(csv_bytes), dtype="string", low_memory=False
        )
        raw_frame = clean_columns(raw_frame)
        validate_universe(universe)

        raw_scope, scope_summary = prepare_raw_equity_scope(raw_frame)
        mapping_results, total_mismatches, key_coverage = compare_fields(
            raw_scope, universe
        )

        normalized_path = REPORT_DIR / f"nse_universe_{audit_id}.csv"
        mapping_path = REPORT_DIR / f"nse_field_mapping_{audit_id}.json"
        summary_path = REPORT_DIR / f"nse_universe_{audit_id}.json"
        universe.to_csv(normalized_path, index=False)

        mapping_status = "PASS" if total_mismatches == 0 else "FAIL"
        mapping_report = {
            "audit_id": audit_id,
            "raw_source_url": capture["url"],
            "raw_file": raw_path.name,
            "raw_is_gzip": is_gzip,
            "content_type": capture["content_type"],
            "content_encoding": capture["content_encoding"],
            **scope_summary,
            "normalized_rows": int(len(universe)),
            "key_coverage": key_coverage,
            "field_mapping": mapping_results,
            "total_field_mismatches": total_mismatches,
            "status": mapping_status,
        }
        mapping_path.write_text(
            json.dumps(mapping_report, indent=2, default=str), encoding="utf-8"
        )

        permitted_counts = {}
        if "Permitted to Trade" in universe.columns:
            permitted_counts = universe["Permitted to Trade"].value_counts(
                dropna=False
            ).to_dict()

        summary = {
            "audit_id": audit_id,
            "audit_time_utc": audit_time.isoformat(),
            "source": "NSE MII Security Master",
            "source_url": capture["url"],
            "raw_file": raw_path.name,
            "normalized_file": normalized_path.name,
            "mapping_file": mapping_path.name,
            **scope_summary,
            "normalized_rows": int(len(universe)),
            "unique_symbols": int(universe["Symbol"].nunique()),
            "marico_found": True,
            "permitted_to_trade_counts": permitted_counts,
            "key_coverage": key_coverage,
            "field_mismatches": total_mismatches,
            "mapping_status": mapping_status,
            "status": mapping_status,
        }
        summary_path.write_text(
            json.dumps(summary, indent=2, default=str), encoding="utf-8"
        )
        print(json.dumps(summary, indent=2, default=str))

        if total_mismatches:
            raise ValueError(f"Field/key mapping mismatches found: {total_mismatches}")
        print("NSE MII RAW FIELD AUDIT: PASS")

    except Exception as error:
        print("NSE MII RAW FIELD AUDIT: FAIL")
        print(f"{type(error).__name__}: {error}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
                    
