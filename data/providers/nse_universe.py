
def fetch_nse_equity_universe(
    timeout: int = 30,
    session: requests.Session | None = None,
    as_of_date: date | None = None,
    lookback_days: int = 7,
) -> pd.DataFrame:
    """Fetch NSE MII master first, then use legacy CSV as fallback."""

    if lookback_days < 0:
        raise ValueError("lookback_days must be zero or greater.")

    client = session or requests.Session()
    client.headers.update(NSE_HEADERS)

    # Homepage is attempted for cookies, but a 403 must not
    # prevent direct access to the NSE archive endpoint.
    try:
        home = client.get(
            "https://www.nseindia.com/",
            timeout=timeout,
        )
        home.raise_for_status()
        print("NSE homepage session: established")
    except requests.RequestException as exc:
        print(
            "NSE homepage session unavailable; "
            "trying archive directly: "
            f"{type(exc).__name__}: {exc}"
        )

    report_date = as_of_date or datetime.now(
        ZoneInfo("Asia/Kolkata")
    ).date()

    mii_errors = []

    for offset in range(lookback_days + 1):
        candidate_date = report_date - timedelta(days=offset)
        date_token = candidate_date.strftime("%d%m%Y")

        url = NSE_MII_SECURITY_URL_TEMPLATE.format(
            date=date_token
        )

        try:
            print(f"Trying NSE MII: {url}")

            response = client.get(url, timeout=timeout)
            response.raise_for_status()

            raw = _read_mii_security_file(response.content)
            result = normalize_nse_mii_security_master(raw)

            if result.empty:
                raise ValueError("MII universe is empty.")

            print(
                f"NSE MII downloaded successfully: "
                f"{len(result)} securities"
            )

            return result

        except Exception as exc:
            error_message = (
                f"{date_token}: {type(exc).__name__}: {exc}"
            )
            mii_errors.append(error_message)
            print(f"MII attempt failed: {error_message}")

    # MII unavailable: retain the previous legacy provider.
    try:
        print("Trying legacy NSE equity master...")

        response = client.get(
            NSE_EQUITY_MASTER_URL,
            timeout=timeout,
        )
        response.raise_for_status()

        raw = pd.read_csv(
            BytesIO(response.content),
            dtype="string",
            low_memory=False,
        )

        return normalize_nse_equity_master(
            raw,
            equity_series_only=True,
        )

    except Exception as exc:
        raise RuntimeError(
            "NSE MII and legacy sources both failed. "
            "MII attempts: " + " | ".join(mii_errors)
            + f" | Legacy error: {type(exc).__name__}: {exc}"
        ) from exc
        
