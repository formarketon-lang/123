"""Validate NSE UDiFF Previous Close against the prior official NSE session.

The caller must supply an independently verified NSE trading-session
calendar and observations covering both the requested date and its
immediately preceding NSE session. Weekday arithmetic is deliberately
not used: holidays and special sessions must come from the calendar.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd


PRICE_TOLERANCE = 0.01
REQUIRED_FIELDS = {
    "Date",
    "Symbol",
    "ISIN",
    "Previous Close",
    "Current Close",
}


class PriorSessionValidationError(ValueError):
    """Raised when prior-session validation input is malformed."""


def _normalize_dates(values: Iterable) -> list[pd.Timestamp]:
    if isinstance(values, (str, bytes)):
        raise PriorSessionValidationError(
            "Trading sessions must be an iterable of dates."
        )
    try:
        raw = list(values)
    except TypeError as exc:
        raise PriorSessionValidationError(
            "Trading sessions must be an iterable of dates."
        ) from exc
    parsed = []
    for value in raw:
        try:
            item = pd.Timestamp(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise PriorSessionValidationError(
                f"Invalid NSE trading-session date: {value!r}"
            ) from exc
        if pd.isna(item):
            raise PriorSessionValidationError(
                f"Invalid NSE trading-session date: {value!r}"
            )
        if item.tzinfo is not None:
            item = item.tz_localize(None)
        parsed.append(item.normalize())
    if len(parsed) != len(set(parsed)):
        raise PriorSessionValidationError(
            "Duplicate NSE trading-session dates are not allowed."
        )
    return sorted(parsed)


def validate_prior_session_prices(
    observations: pd.DataFrame,
    trading_sessions: Iterable,
    *,
    observation_dates: Iterable,
    calendar_verified: bool,
    calendar_source: str | None,
    tolerance: float = PRICE_TOLERANCE,
) -> dict:
    """Compare each row's Previous Close with same-identity prior-session Close.

    Status meanings:
    - PASS: all checked securities match within the explicit tolerance.
    - REVIEW: a security is absent from the prior-session observations.
    - BLOCKED: invalid prices, duplicate identity, or identity/price conflict.
    - UNAVAILABLE: calendar evidence or an entire prior-session observation
      is unavailable. No weekday-based fallback is attempted.

    Include one warm-up NSE session before the first date to be validated,
    and pass only dates whose Previous Close values should be checked in
    observation_dates. Warm-up rows are not themselves validated.
    The supplied calendar must cover every observation date and its prior
    NSE session. A source label alone is not proof; calendar_verified must
    be set only after the caller has independently checked official evidence.
    """

    if not isinstance(observations, pd.DataFrame):
        raise TypeError("observations must be a pandas DataFrame.")
    if observations.empty:
        raise PriorSessionValidationError(
            "Historical observations are empty."
        )
    missing = REQUIRED_FIELDS.difference(observations.columns)
    if missing:
        raise PriorSessionValidationError(
            "Observations are missing required fields: "
            + ", ".join(sorted(missing))
        )
    if not isinstance(calendar_verified, bool):
        raise PriorSessionValidationError(
            "calendar_verified must be an explicit boolean."
        )
    if not np.isfinite(float(tolerance)) or float(tolerance) < 0:
        raise PriorSessionValidationError(
            "Price tolerance must be a finite non-negative number."
        )

    calendar = _normalize_dates(trading_sessions)
    targets = _normalize_dates(observation_dates)
    source = str(calendar_source or "").strip()

    if not calendar_verified or not source or not calendar or not targets:
        return {
            "analysis_status": "UNAVAILABLE",
            "calendar_status": "UNVERIFIED",
            "calendar_source": source or None,
            "tolerance": float(tolerance),
            "checked_dates": 0,
            "pass_count": 0,
            "review_count": 0,
            "blocked_count": 0,
            "unavailable_count": 0,
            "per_date": pd.DataFrame(),
            "per_symbol": pd.DataFrame(),
            "message": (
                "Verified NSE trading-calendar evidence is required; "
                "weekday inference is not permitted."
            ),
        }

    data = observations.copy()
    parsed = pd.to_datetime(data["Date"], errors="coerce")
    if parsed.isna().any():
        raise PriorSessionValidationError(
            "Observations contain invalid trade dates."
        )
    if getattr(parsed.dt, "tz", None) is not None:
        parsed = parsed.dt.tz_localize(None)
    data["Date"] = parsed.dt.normalize()

    for column in ("Symbol", "ISIN"):
        data[column] = (
            data[column].astype("string").str.strip().str.upper()
        )
        if data[column].isna().any() or data[column].eq("").any():
            raise PriorSessionValidationError(
                f"Observations contain missing or blank {column}."
            )

    for column in ("Previous Close", "Current Close"):
        data[column] = pd.to_numeric(data[column], errors="coerce")

    if not data["Date"].isin(calendar).all():
        raise PriorSessionValidationError(
            "Observation dates must all exist in the verified NSE calendar."
        )

    duplicate = data.duplicated(["Date", "Symbol"], keep=False)
    if duplicate.any():
        raise PriorSessionValidationError(
            "Duplicate Symbol observations exist for an NSE session."
        )

    calendar_index = {day: index for index, day in enumerate(calendar)}
    if not set(targets).issubset(set(calendar)):
        raise PriorSessionValidationError(
            "Requested observation dates must exist in the verified NSE calendar."
        )
    if not set(targets).issubset(set(data["Date"])):
        raise PriorSessionValidationError(
            "Requested observation dates are missing from historical observations."
        )

    symbol_rows = []
    date_rows = []

    for current_date in targets:
        index = calendar_index[current_date]
        current = data.loc[data["Date"].eq(current_date)].copy()

        if index == 0:
            date_rows.append({
                "observation_date": current_date.date().isoformat(),
                "previous_session_date": None,
                "status": "UNAVAILABLE",
                "checked_symbols": 0,
                "pass_symbols": 0,
                "review_symbols": 0,
                "blocked_symbols": 0,
                "reason": "Calendar does not include a prior NSE session.",
            })
            continue

        previous_date = calendar[index - 1]
        previous = data.loc[data["Date"].eq(previous_date)].copy()

        if previous.empty:
            date_rows.append({
                "observation_date": current_date.date().isoformat(),
                "previous_session_date": previous_date.date().isoformat(),
                "status": "UNAVAILABLE",
                "checked_symbols": 0,
                "pass_symbols": 0,
                "review_symbols": 0,
                "blocked_symbols": 0,
                "reason": "Entire prior-session observation is unavailable.",
            })
            continue

        previous_by_symbol = previous.set_index("Symbol", drop=False)
        previous_by_isin = previous.set_index("ISIN", drop=False)

        for _, row in current.iterrows():
            symbol = str(row["Symbol"])
            isin = str(row["ISIN"])
            reported_previous = float(row["Previous Close"])
            current_close = float(row["Current Close"])
            status = "PASS"
            reason = "Previous Close matches prior NSE session Close."
            prior_close = np.nan

            if (
                not np.isfinite(reported_previous)
                or not np.isfinite(current_close)
                or reported_previous <= 0
                or current_close <= 0
            ):
                status = "BLOCKED"
                reason = "Current or Previous Close is invalid."
            elif symbol not in previous_by_symbol.index:
                if isin in previous_by_isin.index:
                    status = "BLOCKED"
                    reason = (
                        "ISIN exists in prior session under a different Symbol."
                    )
                else:
                    status = "REVIEW"
                    reason = (
                        "No same-identity prior-session observation; "
                        "possible listing, suspension or missing source row."
                    )
            else:
                prior_row = previous_by_symbol.loc[symbol]
                if isinstance(prior_row, pd.DataFrame):
                    status = "BLOCKED"
                    reason = "Prior session contains duplicate Symbol identity."
                elif str(prior_row["ISIN"]) != isin:
                    status = "BLOCKED"
                    reason = "Symbol matches but ISIN differs from prior session."
                else:
                    prior_close = float(prior_row["Current Close"])
                    if (
                        not np.isfinite(prior_close)
                        or prior_close <= 0
                    ):
                        status = "BLOCKED"
                        reason = "Prior-session Close is invalid."
                    elif abs(reported_previous - prior_close) > tolerance + 1e-9:
                        status = "BLOCKED"
                        reason = (
                            "Bhavcopy Previous Close differs from the "
                            "prior NSE session Close beyond tolerance."
                        )

            symbol_rows.append({
                "observation_date": current_date.date().isoformat(),
                "previous_session_date": previous_date.date().isoformat(),
                "symbol": symbol,
                "isin": isin,
                "reported_previous_close": reported_previous,
                "prior_session_close": prior_close,
                "difference": (
                    reported_previous - prior_close
                    if np.isfinite(prior_close)
                    and np.isfinite(reported_previous)
                    else np.nan
                ),
                "status": status,
                "reason": reason,
            })

        day_rows = [
            item for item in symbol_rows
            if item["observation_date"] == current_date.date().isoformat()
        ]
        statuses = [item["status"] for item in day_rows]
        if "BLOCKED" in statuses:
            day_status = "BLOCKED"
        elif "REVIEW" in statuses:
            day_status = "REVIEW"
        else:
            day_status = "PASS"

        date_rows.append({
            "observation_date": current_date.date().isoformat(),
            "previous_session_date": previous_date.date().isoformat(),
            "status": day_status,
            "checked_symbols": len(day_rows),
            "pass_symbols": statuses.count("PASS"),
            "review_symbols": statuses.count("REVIEW"),
            "blocked_symbols": statuses.count("BLOCKED"),
            "reason": "",
        })

    date_statuses = [item["status"] for item in date_rows]
    if "BLOCKED" in date_statuses:
        overall = "BLOCKED"
    elif "UNAVAILABLE" in date_statuses:
        overall = "UNAVAILABLE"
    elif "REVIEW" in date_statuses:
        overall = "REVIEW"
    else:
        overall = "PASS"

    return {
        "analysis_status": overall,
        "calendar_status": "VERIFIED",
        "calendar_source": source,
        "tolerance": float(tolerance),
        "checked_dates": len(date_rows),
        "pass_count": date_statuses.count("PASS"),
        "review_count": date_statuses.count("REVIEW"),
        "blocked_count": date_statuses.count("BLOCKED"),
        "unavailable_count": date_statuses.count("UNAVAILABLE"),
        "per_date": pd.DataFrame(date_rows),
        "per_symbol": pd.DataFrame(symbol_rows),
        "message": None,
    }
