"""Yahoo Finance historical market-data adapter."""

import pandas as pd
import yfinance as yf

from data.schema import (
    REQUIRED_COLUMNS,
    standardize_ohlcv,
)


SUPPORTED_INTERVALS = {
    "1d", "1wk", "1mo",
    "5m", "15m", "30m", "60m",
}

INTRADAY_INTERVALS = {
    "5m", "15m", "30m", "60m",
}

MAX_INTRADAY_LOOKBACK_DAYS = 60

OHLCV_COLUMNS = {
    "Open", "High", "Low", "Close", "Volume",
}


class YahooDiagnosticMixin:
    """Attach structured diagnostic information to Yahoo errors."""

    def set_diagnostic(
        self,
        code,
        symbol,
        ticker,
        exchange,
        interval,
        start_date,
        end_date,
        message,
        suggested_action,
    ):
        self.diagnostic = {
            "source": "yahoo",
            "code": code,
            "symbol": symbol,
            "ticker": ticker,
            "exchange": exchange,
            "interval": interval,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "message": message,
            "suggested_action": suggested_action,
        }

        super().__init__(
            f"[{code}] {message} "
            f"Suggested action: {suggested_action}"
        )


class YahooDataUnavailableError(YahooDiagnosticMixin, ValueError):
    """Yahoo returned no usable market data."""


class YahooDownloadError(YahooDiagnosticMixin, RuntimeError):
    """Yahoo download request failed."""


class YahooDataValidationError(YahooDiagnosticMixin, ValueError):
    """Yahoo response failed data validation."""


def resolve_yahoo_symbol(symbol: str, exchange: str) -> str:
    """Convert NSE/BSE symbols into Yahoo Finance ticker format."""

    if not isinstance(symbol, str):
        raise ValueError("Stock symbol must be a string.")

    symbol = symbol.strip().upper()

    if not symbol:
        raise ValueError("Stock symbol must not be empty.")

    if exchange not in {"NSE", "BSE"}:
        raise ValueError("Exchange must be NSE or BSE.")

    if symbol.startswith("^"):
        return symbol

    if symbol.endswith((".NS", ".BO")):
        return symbol

    suffix = ".NS" if exchange == "NSE" else ".BO"
    return symbol + suffix


def normalize_yahoo_columns(data: pd.DataFrame) -> pd.DataFrame:
    """Normalize Yahoo Finance single-level or MultiIndex columns."""

    data = data.copy()

    if not isinstance(data.columns, pd.MultiIndex):
        return data

    for level in range(data.columns.nlevels):
        level_values = set(data.columns.get_level_values(level))

        if OHLCV_COLUMNS.issubset(level_values):
            data.columns = data.columns.get_level_values(level)
            return data

    raise ValueError(
        "Unable to identify OHLCV columns "
        "in Yahoo Finance MultiIndex response."
    )


def validate_intraday_date_range(
    start: pd.Timestamp,
    interval: str,
) -> None:
    """Reject intraday requests outside the configured 60-day window."""

    if interval not in INTRADAY_INTERVALS:
        return

    today = (
        pd.Timestamp.now(tz="UTC")
        .tz_localize(None)
        .normalize()
    )

    earliest_allowed = today - pd.Timedelta(
        days=MAX_INTRADAY_LOOKBACK_DAYS
    )

    if start.normalize() < earliest_allowed:
        raise ValueError(
            f"Yahoo Finance {interval} data is limited to the "
            f"configured {MAX_INTRADAY_LOOKBACK_DAYS}-day window. "
            f"Requested start date: {start.date()}. "
            f"Earliest allowed date: {earliest_allowed.date()}."
        )


def _raise_diagnostic(
    error_class,
    code,
    symbol,
    ticker,
    exchange,
    interval,
    start,
    end,
    message,
    suggested_action,
):
    """Raise a structured Yahoo diagnostic error."""

    error = error_class()

    error.set_diagnostic(
        code=code,
        symbol=symbol,
        ticker=ticker,
        exchange=exchange,
        interval=interval,
        start_date=start,
        end_date=end,
        message=message,
        suggested_action=suggested_action,
    )

    raise error


def fetch_yahoo_history(
    symbol: str,
    start_date,
    end_date,
    interval: str = "1d",
    exchange: str = "NSE",
) -> pd.DataFrame:
    """
    Fetch historical OHLCV data from Yahoo Finance.

    Returns:
    Date, Open, High, Low, Close, Volume
    """

    # 1. INPUT VALIDATION

    if not isinstance(symbol, str):
        raise ValueError("Symbol must be a string.")

    symbol = symbol.strip().upper()

    if not symbol:
        raise ValueError("Stock symbol must not be empty.")

    if exchange not in {"NSE", "BSE"}:
        raise ValueError("Exchange must be NSE or BSE.")

    if interval not in SUPPORTED_INTERVALS:
        raise ValueError(
            f"Unsupported interval: {interval}. "
            f"Supported intervals: {sorted(SUPPORTED_INTERVALS)}"
        )

    try:
        start = pd.Timestamp(start_date)
        end = pd.Timestamp(end_date)
    except Exception as error:
        raise ValueError(
            f"Invalid date input: {error}"
        ) from error

    if pd.isna(start) or pd.isna(end):
        raise ValueError("Start date and end date are required.")

    # 2. TIMEZONE NORMALIZATION

    if start.tzinfo is not None:
        start = start.tz_convert("UTC").tz_localize(None)

    if end.tzinfo is not None:
        end = end.tz_convert("UTC").tz_localize(None)

    if start > end:
        raise ValueError(
            "Start date must not be after end date."
        )

    # 3. SYMBOL RESOLUTION

    ticker = resolve_yahoo_symbol(
        symbol=symbol,
        exchange=exchange,
    )

    # 4. INTRADAY AVAILABILITY CHECK

    try:
        validate_intraday_date_range(
            start=start,
            interval=interval,
        )
    except ValueError as error:
        _raise_diagnostic(
            error_class=YahooDataUnavailableError,
            code="INTRADAY_LOOKBACK_EXCEEDED",
            symbol=symbol,
            ticker=ticker,
            exchange=exchange,
            interval=interval,
            start=start,
            end=end,
            message=str(error),
            suggested_action=(
                "Choose a more recent start date or use a daily interval."
            ),
        )

    exclusive_end = end + pd.Timedelta(days=1)

    # 5. DOWNLOAD

    try:
        data = yf.download(
            ticker,
            start=start.strftime("%Y-%m-%d"),
            end=exclusive_end.strftime("%Y-%m-%d"),
            interval=interval,
            auto_adjust=False,
            progress=False,
            threads=False,
        )
    except Exception as error:
        _raise_diagnostic(
            error_class=YahooDownloadError,
            code="YAHOO_DOWNLOAD_FAILED",
            symbol=symbol,
            ticker=ticker,
            exchange=exchange,
            interval=interval,
            start=start,
            end=end,
            message=f"Yahoo Finance download failed: {error}",
            suggested_action=(
                "Check internet access, Yahoo availability, "
                "symbol and requested interval. Retry later if needed."
            ),
        )

    # 6. EMPTY RESPONSE CHECK

    if data is None or data.empty:
        _raise_diagnostic(
            error_class=YahooDataUnavailableError,
            code="NO_DATA_RETURNED",
            symbol=symbol,
            ticker=ticker,
            exchange=exchange,
            interval=interval,
            start=start,
            end=end,
            message=f"No Yahoo Finance data returned for {ticker}.",
            suggested_action=(
                "Verify the ticker, exchange, date range and interval. "
                "The requested historical data may not be available."
            ),
        )

    # 7. RESPONSE NORMALIZATION

    try:
        data = normalize_yahoo_columns(data)
        data = data.reset_index()

        data.columns = [
            str(column) for column in data.columns
        ]

        if "Datetime" in data.columns and "Date" not in data.columns:
            data = data.rename(columns={"Datetime": "Date"})

        if "Date" not in data.columns:
            raise ValueError(
                "Yahoo Finance response has no Date column."
            )

        # 8. COMMON DATA VALIDATION

        standardized = standardize_ohlcv(
            data=data,
            symbol=symbol,
            source="yahoo",
            exchange=exchange,
            timeframe=interval,
        )

    except Exception as error:
        _raise_diagnostic(
            error_class=YahooDataValidationError,
            code="DATA_VALIDATION_FAILED",
            symbol=symbol,
            ticker=ticker,
            exchange=exchange,
            interval=interval,
            start=start,
            end=end,
            message=f"Yahoo response validation failed: {error}",
            suggested_action=(
                "Inspect the returned OHLCV columns, dates, "
                "duplicate rows and price consistency."
            ),
        )

    # 9. PRESERVE EXISTING RS ENGINE INTERFACE

    result = standardized[REQUIRED_COLUMNS].copy()

    result = result[
        (result["Date"] >= start)
        & (result["Date"] < exclusive_end)
    ].copy()

    if result.empty:
        _raise_diagnostic(
            error_class=YahooDataUnavailableError,
            code="NO_VALID_ROWS_IN_DATE_RANGE",
            symbol=symbol,
            ticker=ticker,
            exchange=exchange,
            interval=interval,
            start=start,
            end=end,
            message=(
                "No valid Yahoo Finance rows remain "
                "within the requested date range."
            ),
            suggested_action=(
                "Try a wider date range or verify data availability "
                "for this symbol and interval."
            ),
        )

    # 10. FINAL OUTPUT

    return result.reset_index(drop=True)


