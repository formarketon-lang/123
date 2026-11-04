
from datetime import datetime, timezone
from pathlib import Path
import json

import pandas as pd


INSTRUMENTS = ["MARICO", "NIFTY 50", "NIFTY FMCG"]

OHLCV = ["Open", "High", "Low", "Close", "Volume"]
PRICE_COLUMNS = ["Open", "High", "Low", "Close"]
PRICE_TOLERANCE = 0.01

NSE_DIR = Path("data/raw/nse")
YAHOO_DIR = Path("data/raw/yahoo")
REPORT_ROOT = Path("reports/data_integrity")
HISTORY_FILE = REPORT_ROOT / "audit_history.csv"

KNOWN_NSE_HOLIDAYS = {
    "2026-01-15",
}

KNOWN_NSE_SPECIAL_SESSIONS = {
    "2026-02-01",
}

KNOWN_NSE_REGULAR_SESSIONS = {
    "2025-10-30",
    "2026-01-01",
}


def load_and_normalize(path):
    if not path.exists():
        raise FileNotFoundError(f"Missing data file: {path}")

    df = pd.read_csv(path)

    aliases = {
        "trading date": "Date",
        "timestamp": "Date",
        "ch_timestamp": "Date",
        "open price": "Open",
        "high price": "High",
        "low price": "Low",
        "close price": "Close",
        "total traded quantity": "Volume",
        "tottrdqty": "Volume",
        "tot_traded_qty": "Volume",
        "ch_tot_traded_qty": "Volume",
        "ch_opening_price": "Open",
        "ch_trade_high_price": "High",
        "ch_trade_low_price": "Low",
        "ch_closing_price": "Close",
    }

    rename = {}

    for column in df.columns:
        key = str(column).strip().lower()

        if key in aliases:
            rename[column] = aliases[key]
        else:
            standard = str(column).strip().title()
            if standard in ["Date"] + OHLCV:
                rename[column] = standard

    df = df.rename(columns=rename)

    if "Date" not in df.columns:
        raise ValueError(f"Date column missing in {path}")

    missing_prices = [
        column for column in PRICE_COLUMNS
        if column not in df.columns
    ]

    if missing_prices:
        raise ValueError(
            f"Missing price columns in {path}: {missing_prices}"
        )

    if "Volume" not in df.columns:
        df["Volume"] = pd.NA

    df["Date"] = pd.to_datetime(
        df["Date"],
        errors="coerce",
        dayfirst=True,
    )

    for column in OHLCV:
        df[column] = pd.to_numeric(
            df[column].astype("string").str.replace(
                ",", "", regex=False
            ),
            errors="coerce",
        )

    df = df.dropna(subset=["Date"]).sort_values("Date")

    duplicate_count = int(df["Date"].duplicated().sum())

    if duplicate_count:
        raise ValueError(
            f"Duplicate dates found in {path}: {duplicate_count}"
        )

    return df[["Date"] + OHLCV].reset_index(drop=True)


def is_known_secondary_price_variance(row, instrument):
    """
    Recognize only the independently verified NIFTY 50
    Yahoo secondary-source High difference on 2026-03-06.

    NSE remains the authoritative primary source.
    Global PRICE_TOLERANCE is not changed.
    """

    if instrument != "NIFTY 50":
        return False

    date_key = row["Date"].strftime("%Y-%m-%d")

    if date_key != "2026-03-06":
        return False

    if row["Session_Status"] != "COMMON":
        return False

    # All required OHLC values must be present.
    for column in PRICE_COLUMNS:
        if pd.isna(row[f"{column}_NSE"]):
            return False

        if pd.isna(row[f"{column}_Yahoo"]):
            return False

    nse_high = float(row["High_NSE"])
    yahoo_high = float(row["High_Yahoo"])

    # Verified values: NSE 24700.80, Yahoo 24700.90.
    if round(nse_high, 2) != 24700.80:
        return False

    if round(yahoo_high, 2) != 24700.90:
        return False

    if round(abs(nse_high - yahoo_high), 2) != 0.10:
        return False

    # Open, Low and Close must remain within normal tolerance.
    for column in ["Open", "Low", "Close"]:
        difference = abs(
            float(row[f"{column}_NSE"])
            - float(row[f"{column}_Yahoo"])
        )

        if difference > PRICE_TOLERANCE:
            return False

    return True


def classify_session(row, instrument):
    date_key = row["Date"].strftime("%Y-%m-%d")
    source_status = row["Session_Status"]

    if source_status == "NSE_ONLY":

        if date_key in KNOWN_NSE_SPECIAL_SESSIONS:
            return (
                "SPECIAL_NSE_SESSION_YAHOO_MISSING",
                "Verified special NSE trading session; "
                "Yahoo record is absent. Keep the NSE record.",
            )

        if date_key in KNOWN_NSE_REGULAR_SESSIONS:
            return (
                "NSE_REGULAR_SESSION_YAHOO_MISSING",
                "Verified regular NSE equity trading session; "
                "Yahoo record is absent. NSE remains primary.",
            )

        return (
            "NSE_SESSION_YAHOO_MISSING_UNVERIFIED",
            "NSE file contains this date; Yahoo file does not. "
            "Calendar status has not been independently verified.",
        )

    if source_status == "YAHOO_ONLY":

        if date_key in KNOWN_NSE_HOLIDAYS:
            return (
                "YAHOO_RECORD_ON_KNOWN_NSE_HOLIDAY",
                "Yahoo contains a record on a verified NSE market "
                "holiday. Do not treat it as an NSE trading session.",
            )

        return (
            "YAHOO_ONLY_SESSION_UNVERIFIED",
            "Yahoo file contains this date; NSE file does not. "
            "Calendar status has not been independently verified.",
        )

    if bool(row["OHLC_Missing"]):
        return (
            "OHLC_DATA_MISSING",
            "At least one required OHLC value is missing "
            "in one or both sources on this common date.",
        )

    # Exact, independently verified secondary-source exception.
    if is_known_secondary_price_variance(row, instrument):
        return (
            "KNOWN_SECONDARY_PRICE_VARIANCE",
            "Verified NIFTY 50 variance on 2026-03-06: "
            "NSE High 24700.80 and Yahoo High 24700.90. "
            "NSE is authoritative; Yahoo remains secondary. "
            "Global price tolerance is unchanged.",
        )

    if bool(row["OHLC_Mismatch"]):
        return (
            "OHLC_PRICE_DIFFERENCE",
            "At least one OHLC value differs by more than "
            f"{PRICE_TOLERANCE}.",
        )

    if bool(row["Volume_Mismatch"]):
        return (
            "VOLUME_DIFFERENCE",
            "Both sources contain this date, but Volume values differ.",
        )

    if row["Volume_Status"] == "NOT_COMPARABLE":
        return (
            "OHLC_MATCH_VOLUME_NOT_AVAILABLE",
            "OHLC values are within tolerance. Volume is missing "
            "in one or both sources and cannot be compared.",
        )

    if date_key in KNOWN_NSE_SPECIAL_SESSIONS:
        return (
            "SPECIAL_NSE_SESSION_MATCHED",
            "Verified special NSE trading session is present "
            "in both sources; OHLC and comparable Volume match.",
        )

    return (
        "VERIFIED_MATCH",
        "Both sources contain this date; OHLC and "
        "comparable Volume match.",
    )


def compare_sources(nse, yahoo, instrument):
    merged = nse.merge(
        yahoo,
        on="Date",
        how="outer",
        suffixes=("_NSE", "_Yahoo"),
        indicator=True,
    ).sort_values("Date").reset_index(drop=True)

    merged["Session_Status"] = merged["_merge"].map({
        "both": "COMMON",
        "left_only": "NSE_ONLY",
        "right_only": "YAHOO_ONLY",
    })

    common_rows = merged["_merge"] == "both"

    missing_ohlc = pd.Series(False, index=merged.index)

    for column in PRICE_COLUMNS:
        nse_col = f"{column}_NSE"
        yahoo_col = f"{column}_Yahoo"

        missing_ohlc |= (
            common_rows
            & (
                merged[nse_col].isna()
                | merged[yahoo_col].isna()
            )
        )

        merged[f"{column}_Difference"] = (
            merged[nse_col] - merged[yahoo_col]
        )

    merged["OHLC_Missing"] = missing_ohlc

    price_mismatch = pd.Series(False, index=merged.index)

    for column in PRICE_COLUMNS:
        difference = merged[f"{column}_Difference"].abs()

        price_mismatch |= (
            common_rows
            & difference.notna()
            & (difference > PRICE_TOLERANCE)
        )

    merged["OHLC_Mismatch"] = price_mismatch

    nse_volume = merged["Volume_NSE"]
    yahoo_volume = merged["Volume_Yahoo"]

    both_volumes_available = (
        nse_volume.notna() & yahoo_volume.notna()
    )

    merged["Volume_Mismatch"] = (
        common_rows
        & both_volumes_available
        & (nse_volume != yahoo_volume)
    )

    merged["Volume_Status"] = "NO_COUNTERPART"

    merged.loc[
        common_rows & ~both_volumes_available,
        "Volume_Status",
    ] = "NOT_COMPARABLE"

    merged.loc[
        common_rows
        & both_volumes_available
        & merged["Volume_Mismatch"],
        "Volume_Status",
    ] = "MISMATCH"

    merged.loc[
        common_rows
        & both_volumes_available
        & ~merged["Volume_Mismatch"],
        "Volume_Status",
    ] = "MATCH"

    classifications = merged.apply(
        lambda row: classify_session(row, instrument),
        axis=1,
    )

    merged["Session_Classification"] = [
        item[0] for item in classifications
    ]

    merged["Classification_Reason"] = [
        item[1] for item in classifications
    ]

    common = int(common_rows.sum())
    nse_only = int((merged["_merge"] == "left_only").sum())
    yahoo_only = int((merged["_merge"] == "right_only").sum())

    classification = merged["Session_Classification"]

    special_missing = int(
        (
            classification
            == "SPECIAL_NSE_SESSION_YAHOO_MISSING"
        ).sum()
    )

    holiday_yahoo_records = int(
        (
            classification
            == "YAHOO_RECORD_ON_KNOWN_NSE_HOLIDAY"
        ).sum()
    )

    regular_missing = int(
        (
            classification
            == "NSE_REGULAR_SESSION_YAHOO_MISSING"
        ).sum()
    )

    known_price_variance = int(
        (
            classification
            == "KNOWN_SECONDARY_PRICE_VARIANCE"
        ).sum()
    )

    unverified_nse_missing = int(
        (
            classification
            == "NSE_SESSION_YAHOO_MISSING_UNVERIFIED"
        ).sum()
    )

    unverified_yahoo_only = int(
        (
            classification
            == "YAHOO_ONLY_SESSION_UNVERIFIED"
        ).sum()
    )

    # Verified regular sessions are accepted exceptions too.
    expected_exceptions = (
        special_missing
        + regular_missing
        + holiday_yahoo_records
    )

    raw_ohlc_mismatches = int(
        merged["OHLC_Mismatch"].sum()
    )

    unresolved_ohlc_mismatches = max(
        0,
        raw_ohlc_mismatches - known_price_variance,
    )

    summary = {
        "instrument": instrument,
        "nse_rows": len(nse),
        "yahoo_rows": len(yahoo),
        "common_sessions": common,
        "nse_only_sessions": nse_only,
        "yahoo_only_sessions": yahoo_only,

        "ohlc_missing_sessions": int(
            merged["OHLC_Missing"].sum()
        ),

        "ohlc_mismatch_sessions": raw_ohlc_mismatches,

        "known_secondary_price_variance_sessions": (
            known_price_variance
        ),

        "unresolved_ohlc_mismatch_sessions": (
            unresolved_ohlc_mismatches
        ),

        "volume_mismatch_sessions": int(
            merged["Volume_Mismatch"].sum()
        ),

        "volume_not_comparable_sessions": int(
            (
                common_rows
                & (merged["Volume_Status"] == "NOT_COMPARABLE")
            ).sum()
        ),

        "known_nse_holiday_yahoo_records": holiday_yahoo_records,
        "known_special_session_yahoo_missing": special_missing,
        "known_regular_session_yahoo_missing": regular_missing,

        "unverified_nse_missing_sessions": unverified_nse_missing,
        "unverified_yahoo_only_sessions": unverified_yahoo_only,

        "expected_exception_sessions": expected_exceptions,

        "nse_first_date": (
            str(nse["Date"].min().date())
            if not nse.empty else None
        ),

        "nse_last_date": (
            str(nse["Date"].max().date())
            if not nse.empty else None
        ),

        "yahoo_first_date": (
            str(yahoo["Date"].min().date())
            if not yahoo.empty else None
        ),

        "yahoo_last_date": (
            str(yahoo["Date"].max().date())
            if not yahoo.empty else None
        ),
    }

    # NSE is the authoritative primary source.
    nse_ohlc_missing_mask = nse[PRICE_COLUMNS].isna().any(axis=1)

    nse_ohlc_invalid_mask = (
        (nse["High"] < nse[["Open", "Close"]].max(axis=1))
        | (nse["Low"] > nse[["Open", "Close"]].min(axis=1))
        | (nse["High"] < nse["Low"])
        | (nse[PRICE_COLUMNS] <= 0).any(axis=1)
    ).fillna(False)

    primary_missing = int(nse_ohlc_missing_mask.sum())
    primary_invalid = int(nse_ohlc_invalid_mask.sum())

    summary["primary_nse_ohlc_missing_sessions"] = primary_missing
    summary["primary_nse_invalid_ohlc_sessions"] = primary_invalid

    yahoo_ohlc_missing_mask = (
        merged[[f"{column}_Yahoo" for column in PRICE_COLUMNS]]
        .isna()
        .any(axis=1)
    )

    nse_ohlc_present_mask = (
        merged[[f"{column}_NSE" for column in PRICE_COLUMNS]]
        .notna()
        .all(axis=1)
    )

    secondary_ohlc_missing = int(
        (
            common_rows
            & nse_ohlc_present_mask
            & yahoo_ohlc_missing_mask
        ).sum()
    )

    summary["secondary_yahoo_ohlc_missing_sessions"] = (
        secondary_ohlc_missing
    )

    primary_data_is_valid = (
        not nse.empty
        and primary_missing == 0
        and primary_invalid == 0
    )

    # Only verified exceptions are accepted.
    # Unknown session gaps and unresolved mismatches remain REVIEW.
    has_secondary_findings = (
        (nse_only + yahoo_only) > expected_exceptions
        or summary["ohlc_missing_sessions"] > 0
        or unresolved_ohlc_mismatches > 0
        or summary["volume_mismatch_sessions"] > 0
        or secondary_ohlc_missing > 0
    )

    if not primary_data_is_valid:
        summary["status"] = "REVIEW"

    elif has_secondary_findings:
        summary["status"] = "REVIEW"

    elif summary["volume_not_comparable_sessions"] > 0:
        summary["status"] = "PASS_WITH_SECONDARY_WARNINGS"

    elif expected_exceptions > 0 or known_price_variance > 0:
        summary["status"] = "PASS_WITH_EXPECTED_EXCEPTIONS"

    else:
        summary["status"] = "MATCH"

    detail = merged.drop(columns=["_merge"])

    return summary, detail


def main():
    audit_time = datetime.now(timezone.utc)
    audit_id = audit_time.strftime("%Y%m%d_%H%M%S")

    report_dir = REPORT_ROOT / audit_id
    report_dir.mkdir(parents=True, exist_ok=True)

    summaries = []
    details = []

    for instrument in INSTRUMENTS:
        safe_name = instrument.replace(" ", "_")

        nse_file = NSE_DIR / f"{safe_name}_nse.csv"
        yahoo_file = YAHOO_DIR / f"{safe_name}_yahoo.csv"

        print(f"\nAuditing: {instrument}")

        nse = load_and_normalize(nse_file)
        yahoo = load_and_normalize(yahoo_file)

        summary, detail = compare_sources(
            nse,
            yahoo,
            instrument,
        )

        summary["audit_id"] = audit_id
        summary["audit_time_utc"] = audit_time.isoformat()

        summaries.append(summary)

        detail.insert(0, "Instrument", instrument)
        details.append(detail)

        print(summary)
        print("\nClassification counts:")
        print(
            detail["Session_Classification"]
            .value_counts(dropna=False)
            .to_string()
        )

    summary_df = pd.DataFrame(summaries)
    detail_df = pd.concat(details, ignore_index=True)

    if HISTORY_FILE.exists():
        previous = pd.read_csv(HISTORY_FILE)
        previous = previous.sort_values("audit_time_utc")

        for index, row in summary_df.iterrows():
            old = previous[
                previous["instrument"] == row["instrument"]
            ]

            if not old.empty:
                previous_row = old.iloc[-1]

                summary_df.loc[
                    index, "previous_common_sessions"
                ] = previous_row["common_sessions"]

                summary_df.loc[
                    index, "change_in_common_sessions"
                ] = (
                    row["common_sessions"]
                    - previous_row["common_sessions"]
                )

                summary_df.loc[
                    index, "previous_ohlc_mismatches"
                ] = previous_row["ohlc_mismatch_sessions"]

    summary_path = report_dir / "summary.csv"
    detail_path = report_dir / "daily_comparison.csv"
    json_path = report_dir / "audit.json"

    summary_df.to_csv(summary_path, index=False)
    detail_df.to_csv(detail_path, index=False)

    with open(json_path, "w", encoding="utf-8") as file:
        json.dump(
            summary_df.to_dict(orient="records"),
            file,
            indent=2,
            default=str,
        )

    REPORT_ROOT.mkdir(parents=True, exist_ok=True)

    if HISTORY_FILE.exists():
        old_history = pd.read_csv(HISTORY_FILE)

        history = pd.concat(
            [old_history, summary_df],
            ignore_index=True,
        )
    else:
        history = summary_df.copy()

    history.to_csv(HISTORY_FILE, index=False)

    print("\n========== AUDIT COMPLETED ==========")
    print("Audit ID:", audit_id)
    print("Summary:", summary_path)
    print("Daily comparison:", detail_path)
    print("Historical log:", HISTORY_FILE)


if __name__ == "__main__":
    main()
