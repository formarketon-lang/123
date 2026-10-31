
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


def load_and_normalize(path):
    if not path.exists():
        raise FileNotFoundError(f"Missing data file: {path}")

    df = pd.read_csv(path)

    # Normalize column names.
    aliases = {
        "trading date": "Date",
        "timestamp": "Date",
        "ch_timestamp": "Date",
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

    df["Date"] = pd.to_datetime(
        df["Date"],
        errors="coerce",
        dayfirst=True,
    )

    for column in OHLCV:
        if column not in df.columns:
            df[column] = pd.NA

        df[column] = pd.to_numeric(
            df[column].astype(str).str.replace(",", "", regex=False),
            errors="coerce",
        )

    df = df.dropna(subset=["Date"])
    df = df.sort_values("Date")
    df = df.drop_duplicates("Date", keep="last")

    return df[["Date"] + OHLCV].reset_index(drop=True)


def compare_sources(nse, yahoo, instrument):
    merged = nse.merge(
        yahoo,
        on="Date",
        how="outer",
        suffixes=("_NSE", "_Yahoo"),
        indicator=True,
    ).sort_values("Date")

    merged["Session_Status"] = merged["_merge"].map({
        "both": "COMMON",
        "left_only": "NSE_ONLY",
        "right_only": "YAHOO_ONLY",
    })

    for column in PRICE_COLUMNS:
        nse_col = f"{column}_NSE"
        yahoo_col = f"{column}_Yahoo"

        merged[f"{column}_Difference"] = (
            merged[nse_col] - merged[yahoo_col]
        )

    price_mismatch = pd.Series(False, index=merged.index)

    for column in PRICE_COLUMNS:
        difference = merged[f"{column}_Difference"].abs()
        price_mismatch |= (
            (merged["_merge"] == "both")
            & difference.notna()
            & (difference > PRICE_TOLERANCE)
        )

    merged["OHLC_Mismatch"] = price_mismatch

    volume_difference = (
        merged["Volume_NSE"] - merged["Volume_Yahoo"]
    )

    merged["Volume_Mismatch"] = (
        (merged["_merge"] == "both")
        & volume_difference.notna()
        & (volume_difference != 0)
    )

    common = int((merged["_merge"] == "both").sum())
    nse_only = int((merged["_merge"] == "left_only").sum())
    yahoo_only = int((merged["_merge"] == "right_only").sum())

    summary = {
        "instrument": instrument,
        "nse_rows": len(nse),
        "yahoo_rows": len(yahoo),
        "common_sessions": common,
        "nse_only_sessions": nse_only,
        "yahoo_only_sessions": yahoo_only,
        "ohlc_mismatch_sessions": int(merged["OHLC_Mismatch"].sum()),
        "volume_mismatch_sessions": int(merged["Volume_Mismatch"].sum()),
        "nse_first_date": str(nse["Date"].min().date()) if not nse.empty else None,
        "nse_last_date": str(nse["Date"].max().date()) if not nse.empty else None,
        "yahoo_first_date": str(yahoo["Date"].min().date()) if not yahoo.empty else None,
        "yahoo_last_date": str(yahoo["Date"].max().date()) if not yahoo.empty else None,
    }

    summary["status"] = (
        "MATCH"
        if nse_only == 0
        and yahoo_only == 0
        and summary["ohlc_mismatch_sessions"] == 0
        and summary["volume_mismatch_sessions"] == 0
        else "REVIEW"
    )

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

    summary_df = pd.DataFrame(summaries)
    detail_df = pd.concat(details, ignore_index=True)

    # Compare this audit with the previous audit.
    if HISTORY_FILE.exists():
        previous = pd.read_csv(HISTORY_FILE)

        previous = previous.sort_values("audit_time_utc")

        for index, row in summary_df.iterrows():
            old = previous[
                previous["instrument"] == row["instrument"]
            ]

            if not old.empty:
                previous_row = old.iloc[-1]

                summary_df.loc[index, "previous_common_sessions"] = (
                    previous_row["common_sessions"]
                )
                summary_df.loc[index, "change_in_common_sessions"] = (
                    row["common_sessions"]
                    - previous_row["common_sessions"]
                )
                summary_df.loc[index, "previous_ohlc_mismatches"] = (
                    previous_row["ohlc_mismatch_sessions"]
                )

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

    # Append this audit to the permanent history.
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
  
