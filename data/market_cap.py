
def enrich_nse_universe_with_amfi(universe, amfi_data):
    """Match AMFI categories to NSE EQ securities using ISIN and symbol."""
    required = {"Symbol", "ISIN", "Series"}
    missing = required - set(universe.columns)

    if missing:
        raise ValueError(
            f"NSE universe missing columns: {sorted(missing)}"
        )

    if not isinstance(amfi_data, pd.DataFrame):
        raise ValueError("AMFI data must be a DataFrame")

    required_amfi = {
        "ISIN", "AMFI NSE Symbol", "Market Cap Category"
    }
    if required_amfi - set(amfi_data.columns):
        amfi_data = normalize_amfi_market_cap(amfi_data)

    output = universe.copy()

    eligible_mask = (
        output["Series"].astype(str).str.strip().str.upper().eq("EQ")
        & output["ISIN"].notna()
    )

    eligible = output.loc[eligible_mask].copy()
    eligible["ISIN"] = (
        eligible["ISIN"].astype(str).str.strip().str.upper()
    )
    eligible["Symbol"] = (
        eligible["Symbol"].astype(str).str.strip().str.upper()
    )

    if eligible["ISIN"].duplicated().any():
        raise ValueError("Duplicate ISIN found in NSE EQ universe")

    amfi = amfi_data.copy()
    amfi["ISIN"] = (
        amfi["ISIN"].astype(str).str.strip().str.upper()
    )
    amfi["AMFI NSE Symbol"] = (
        amfi["AMFI NSE Symbol"].astype(str).str.strip().str.upper()
    )

    if amfi["ISIN"].duplicated().any():
        raise ValueError("Duplicate ISIN found in AMFI data")

    # Remove old enrichment columns before merging.
    # This prevents Pandas from creating _x and _y suffixes.
    enrichment_columns = [
        "AMFI NSE Symbol",
        "Market Cap Category",
        "Market Cap Match Status",
        "AMFI Period",
        "AMFI Source",
        "Market Cap Source",
        "Average Market Cap (Rs. Cr.)",
        "AMFI Average Market Cap (₹ Cr)",
    ]

    eligible = eligible.drop(
        columns=[
            column for column in enrichment_columns
            if column in eligible.columns
        ],
        errors="ignore",
    )

    merged = eligible.merge(
        amfi,
        on="ISIN",
        how="left",
        validate="one_to_one",
    )

    has_isin_match = merged["AMFI NSE Symbol"].notna()
    exact_match = (
        has_isin_match
        & merged["Symbol"].eq(merged["AMFI NSE Symbol"])
    )

    merged["Market Cap Match Status"] = "NO_AMFI_MATCH"
    merged.loc[
        has_isin_match & ~exact_match,
        "Market Cap Match Status",
    ] = "ISIN_SYMBOL_MISMATCH"

    merged.loc[
        exact_match,
        "Market Cap Match Status",
    ] = "MATCHED"

    merged["Market Cap Category"] = (
        merged["Market Cap Category"].where(exact_match)
    )

    merged["AMFI Period"] = AMFI_PERIOD
    merged["AMFI Source"] = AMFI_SOURCE_NAME

    output = output.drop(
        columns=[
            column for column in enrichment_columns
            if column in output.columns
        ],
        errors="ignore",
    )

    output["Market Cap Category"] = pd.NA
    output["Market Cap Match Status"] = "NO_AMFI_MATCH"
    output["AMFI Period"] = AMFI_PERIOD
    output["AMFI Source"] = AMFI_SOURCE_NAME
    output["AMFI NSE Symbol"] = pd.NA

    if "Average Market Cap (Rs. Cr.)" in merged.columns:
        output["Average Market Cap (Rs. Cr.)"] = pd.NA

    output.loc[
        eligible_mask,
        "Market Cap Category",
    ] = merged["Market Cap Category"].to_numpy()

    output.loc[
        eligible_mask,
        "Market Cap Match Status",
    ] = merged["Market Cap Match Status"].to_numpy()

    output.loc[
        eligible_mask,
        "AMFI NSE Symbol",
    ] = merged["AMFI NSE Symbol"].to_numpy()

    if "Average Market Cap (Rs. Cr.)" in merged.columns:
        output.loc[
            eligible_mask,
            "Average Market Cap (Rs. Cr.)",
        ] = merged["Average Market Cap (Rs. Cr.)"].to_numpy()

    return output
    
