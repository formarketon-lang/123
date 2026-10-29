"""Manually run a live Yahoo Finance data-fetch check."""

from datetime import date, timedelta

from data.yahoo_adapter import fetch_yahoo_history


def main():
    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    print("Checking live Yahoo Finance data...")
    print("Symbol: HINDUNILVR")
    print(f"Date range: {start_date} to {end_date}")

    try:
        data = fetch_yahoo_history(
            symbol="HINDUNILVR",
            start_date=start_date,
            end_date=end_date,
            interval="1d",
            exchange="NSE",
        )

        print("\nSUCCESS: Yahoo Finance returned data.")
        print(f"Rows: {len(data)}")
        print(f"Columns: {list(data.columns)}")
        print("\nLatest rows:")
        print(data.tail(5).to_string(index=False))

    except Exception as exc:
        print("\nLIVE FETCH FAILED")
        print(f"Error type: {type(exc).__name__}")
        print(f"Details: {exc}")


if __name__ == "__main__":
    main()
      
