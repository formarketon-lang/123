from pathlib import Path

from data.providers.yahoo_downloader import (
    download_yahoo_history,
    save_yahoo_csv,
)


START_DATE = "2025-10-31"
END_DATE = "2026-10-29"

INSTRUMENTS = [
    "MARICO",
    "NIFTY 50",
    "NIFTY FMCG",
]


def main():
    successful = []
    failed = []

    for name in INSTRUMENTS:
        print(f"\nChecking Yahoo data: {name}")

        try:
            df = download_yahoo_history(
                name,
                START_DATE,
                END_DATE,
            )

            if df.empty:
                raise ValueError("Downloaded dataset is empty.")

            file_path = save_yahoo_csv(df, name)

            result = {
                "instrument": name,
                "rows": len(df),
                "first_date": str(df["Date"].min().date()),
                "last_date": str(df["Date"].max().date()),
                "file": file_path,
            }

            successful.append(result)
            print("PASS:", result)

        except Exception as exc:
            failed.append({
                "instrument": name,
                "error": str(exc),
            })
            print("FAIL:", name, str(exc))

    print("\n========== YAHOO LIVE CHECK ==========")
    print("Successful:", len(successful))
    print("Failed:", len(failed))

    if failed:
        print("\nFailures:", failed)
        raise SystemExit(1)

    print("\nAll Yahoo downloads completed successfully.")


if __name__ == "__main__":
    main()
  
