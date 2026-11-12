
def validate_redirect_history(
    source_url: str,
    redirect_chain: list,
    final_url: str,
    exchange: str,
) -> tuple[bool, str]:
    """Validate redirect history without counting final URL twice."""

    if not isinstance(redirect_chain, list):
        return False, "Redirect chain must be a list."

    if len(redirect_chain) > MAX_REDIRECTS:
        return False, "Redirect chain exceeds the maximum of five redirects."

    history = [source_url, *redirect_chain]

    if not all(
        isinstance(url, str) and url.strip()
        for url in [*history, final_url]
    ):
        return False, "Redirect chain contains an invalid URL."

    if not all(
        approved_source_url(url, exchange)
        for url in [*history, final_url]
    ):
        return False, "Unapproved or invalid source URL in provenance."

    # Check actual navigation history only.
    # final_url is already the last redirect target when redirects exist.
    if len(set(history)) != len(history):
        return False, "Redirect chain contains a repeated URL or loop."

    if redirect_chain:
        if redirect_chain[-1] != final_url:
            return False, "Final URL does not match the last redirect target."
    elif source_url != final_url:
        return False, (
            "Final URL differs from source URL "
            "but no redirect was recorded."
        )

    return True, ""
    
